


SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;


COMMENT ON SCHEMA "public" IS 'standard public schema';



CREATE EXTENSION IF NOT EXISTS "pg_graphql" WITH SCHEMA "graphql";






CREATE EXTENSION IF NOT EXISTS "pg_stat_statements" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "pgcrypto" WITH SCHEMA "extensions";






CREATE EXTENSION IF NOT EXISTS "supabase_vault" WITH SCHEMA "vault";






CREATE EXTENSION IF NOT EXISTS "uuid-ossp" WITH SCHEMA "extensions";






CREATE TYPE "public"."ambivalence_lean" AS ENUM (
    'toward_change',
    'toward_status_quo',
    'both'
);


ALTER TYPE "public"."ambivalence_lean" OWNER TO "postgres";


CREATE TYPE "public"."consent_kind" AS ENUM (
    'data_use',
    'microphone',
    'camera'
);


ALTER TYPE "public"."consent_kind" OWNER TO "postgres";


CREATE TYPE "public"."disclosure_level" AS ENUM (
    'guarded',
    'medium',
    'high'
);


ALTER TYPE "public"."disclosure_level" OWNER TO "postgres";


CREATE TYPE "public"."evaluation_status" AS ENUM (
    'running',
    'completed',
    'failed'
);


ALTER TYPE "public"."evaluation_status" OWNER TO "postgres";


CREATE TYPE "public"."facial_expression" AS ENUM (
    'neutral',
    'happy',
    'sad',
    'angry',
    'disgust',
    'fear',
    'surprise'
);


ALTER TYPE "public"."facial_expression" OWNER TO "postgres";


CREATE TYPE "public"."feedback_kind" AS ENUM (
    'strength',
    'improvement',
    'alternative_response'
);


ALTER TYPE "public"."feedback_kind" OWNER TO "postgres";


CREATE TYPE "public"."global_dimension" AS ENUM (
    'cultivating_change_talk',
    'softening_sustain_talk',
    'partnership',
    'empathy'
);


ALTER TYPE "public"."global_dimension" OWNER TO "postgres";


CREATE TYPE "public"."mi_process" AS ENUM (
    'engaging',
    'focusing',
    'evoking',
    'planning',
    'insufficient_evidence'
);


ALTER TYPE "public"."mi_process" OWNER TO "postgres";


CREATE TYPE "public"."miti_code" AS ENUM (
    'GI',
    'P',
    'PWP',
    'Q',
    'SR',
    'CR',
    'AF',
    'SEEK',
    'EA',
    'CONFRONT'
);


ALTER TYPE "public"."miti_code" OWNER TO "postgres";


CREATE TYPE "public"."review_status" AS ENUM (
    'draft',
    'reviewed',
    'approved'
);


ALTER TYPE "public"."review_status" OWNER TO "postgres";


CREATE TYPE "public"."scenario_visibility" AS ENUM (
    'class',
    'catalog'
);


ALTER TYPE "public"."scenario_visibility" OWNER TO "postgres";


CREATE TYPE "public"."session_status" AS ENUM (
    'in_progress',
    'completed'
);


ALTER TYPE "public"."session_status" OWNER TO "postgres";


CREATE TYPE "public"."speaker" AS ENUM (
    'counselor',
    'client'
);


ALTER TYPE "public"."speaker" OWNER TO "postgres";


CREATE TYPE "public"."topic_source" AS ENUM (
    'main_problem',
    'history_impact',
    'expectation_change_context',
    'hidden_fact'
);


ALTER TYPE "public"."topic_source" OWNER TO "postgres";


CREATE TYPE "public"."user_role" AS ENUM (
    'student',
    'lecturer',
    'admin'
);


ALTER TYPE "public"."user_role" OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."build_scenario_snapshot"("p_scenario_id" bigint) RETURNS "jsonb"
    LANGUAGE "sql" STABLE
    AS $$
    SELECT jsonb_build_object(
        'scenario',      to_jsonb(sc) - 'owner_id' - 'deleted_at',
        'persona',       to_jsonb(p)  - 'scenario_id',
        'case',          to_jsonb(c)  - 'scenario_id',
        'initial_state', to_jsonb(i)  - 'scenario_id',
        'hidden_facts',  COALESCE((SELECT jsonb_agg(to_jsonb(h) - 'id' - 'scenario_id' ORDER BY h.sort_order)
                                   FROM scenario_hidden_facts h WHERE h.scenario_id = sc.id), '[]'::jsonb))
    FROM scenarios sc
    JOIN scenario_personas p       ON p.scenario_id = sc.id
    JOIN scenario_cases c          ON c.scenario_id = sc.id
    JOIN scenario_initial_states i ON i.scenario_id = sc.id
    WHERE sc.id = p_scenario_id;
$$;


ALTER FUNCTION "public"."build_scenario_snapshot"("p_scenario_id" bigint) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."check_miti_rules"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    v_speaker      speaker;
    v_turn_session bigint;
    v_eval_session bigint;
BEGIN
    SELECT t.speaker, t.session_id INTO v_speaker, v_turn_session FROM turns t WHERE t.id = NEW.turn_id;
    SELECT e.session_id INTO v_eval_session FROM evaluations e WHERE e.id = NEW.evaluation_id;

    IF v_turn_session IS DISTINCT FROM v_eval_session THEN
        RAISE EXCEPTION 'Turn % does not belong to the session of evaluation %', NEW.turn_id, NEW.evaluation_id;
    END IF;
    IF v_speaker <> 'counselor' THEN
        RAISE EXCEPTION 'MITI codes apply to counselor turns only (turn %)', NEW.turn_id;
    END IF;

    IF NEW.code IN ('SR', 'CR') AND EXISTS (
        SELECT 1 FROM miti_codes m
        WHERE m.evaluation_id = NEW.evaluation_id AND m.turn_id = NEW.turn_id
          AND m.code IN ('SR', 'CR') AND m.id <> NEW.id) THEN
        RAISE EXCEPTION 'A turn may have only one reflection code (SR or CR)';
    END IF;
    IF NEW.code IN ('P', 'PWP') AND EXISTS (
        SELECT 1 FROM miti_codes m
        WHERE m.evaluation_id = NEW.evaluation_id AND m.turn_id = NEW.turn_id
          AND m.code IN ('P', 'PWP') AND m.id <> NEW.id) THEN
        RAISE EXCEPTION 'A turn may have only one persuasion code (P or PWP)';
    END IF;
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."check_miti_rules"() OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."purge_deleted_sessions"("days" integer DEFAULT 30) RETURNS integer
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    n integer;
BEGIN
    DELETE FROM sessions s
    WHERE s.deleted_at < now() - make_interval(days => days)
      AND NOT EXISTS (
            SELECT 1 FROM sessions c
            WHERE c.parent_session_id = s.id
              AND (c.deleted_at IS NULL OR c.deleted_at >= now() - make_interval(days => days)));
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;


ALTER FUNCTION "public"."purge_deleted_sessions"("days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."purge_old_refresh_tokens"("days" integer DEFAULT 7) RETURNS integer
    LANGUAGE "plpgsql"
    AS $$
DECLARE
    n integer;
BEGIN
    DELETE FROM refresh_tokens
    WHERE LEAST(expires_at, COALESCE(revoked_at, expires_at)) < now() - make_interval(days => days);
    GET DIAGNOSTICS n = ROW_COUNT;
    RETURN n;
END;
$$;


ALTER FUNCTION "public"."purge_old_refresh_tokens"("days" integer) OWNER TO "postgres";


CREATE OR REPLACE FUNCTION "public"."set_updated_at"() RETURNS "trigger"
    LANGUAGE "plpgsql"
    AS $$
BEGIN
    NEW.updated_at := now();
    RETURN NEW;
END;
$$;


ALTER FUNCTION "public"."set_updated_at"() OWNER TO "postgres";

SET default_tablespace = '';

SET default_table_access_method = "heap";


CREATE TABLE IF NOT EXISTS "public"."class_members" (
    "id" bigint NOT NULL,
    "class_id" bigint NOT NULL,
    "user_id" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deleted_at" timestamp with time zone
);


ALTER TABLE "public"."class_members" OWNER TO "postgres";


ALTER TABLE "public"."class_members" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."class_members_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."class_scenarios" (
    "id" bigint NOT NULL,
    "class_id" bigint NOT NULL,
    "scenario_id" bigint NOT NULL,
    "assigned_by" bigint NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."class_scenarios" OWNER TO "postgres";


ALTER TABLE "public"."class_scenarios" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."class_scenarios_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."classes" (
    "id" bigint NOT NULL,
    "name" "text" NOT NULL,
    "academic_year" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deleted_at" timestamp with time zone
);


ALTER TABLE "public"."classes" OWNER TO "postgres";


ALTER TABLE "public"."classes" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."classes_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."client_state_log" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "turn_id" bigint,
    "emotion_type" "text" NOT NULL,
    "emotion_cause" "text",
    "disclosure_level" "public"."disclosure_level" NOT NULL,
    "disclosure_trigger" "text",
    "reasons_to_change" "text",
    "reasons_to_maintain" "text",
    "ambivalence_lean" "public"."ambivalence_lean" NOT NULL,
    "discord_present" boolean NOT NULL,
    "discord_context" "text",
    "discord_response" "text",
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."client_state_log" OWNER TO "postgres";


ALTER TABLE "public"."client_state_log" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."client_state_log_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."consents" (
    "id" bigint NOT NULL,
    "user_id" bigint NOT NULL,
    "kind" "public"."consent_kind" NOT NULL,
    "version" "text" NOT NULL,
    "granted" boolean NOT NULL,
    "recorded_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."consents" OWNER TO "postgres";


ALTER TABLE "public"."consents" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."consents_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."evaluations" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "status" "public"."evaluation_status" DEFAULT 'running'::"public"."evaluation_status" NOT NULL,
    "guideline_version" "text" NOT NULL,
    "model_version" "text",
    "assessed_duration_seconds" integer,
    "limitation_notes" "text",
    "session_summary" "text",
    "completed_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "evaluations_assessed_duration_seconds_check" CHECK (("assessed_duration_seconds" >= 0))
);


ALTER TABLE "public"."evaluations" OWNER TO "postgres";


ALTER TABLE "public"."evaluations" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."evaluations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."face_observations" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "time_ms" integer NOT NULL,
    "turn_id" bigint,
    "expression" "public"."facial_expression",
    "score" numeric(5,4),
    "usable" boolean DEFAULT true NOT NULL,
    "note" "text",
    CONSTRAINT "face_observations_score_check" CHECK ((("score" >= (0)::numeric) AND ("score" <= (1)::numeric))),
    CONSTRAINT "face_observations_time_ms_check" CHECK (("time_ms" >= 0))
);


ALTER TABLE "public"."face_observations" OWNER TO "postgres";


ALTER TABLE "public"."face_observations" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."face_observations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."feedback_items" (
    "id" bigint NOT NULL,
    "evaluation_id" bigint NOT NULL,
    "kind" "public"."feedback_kind" NOT NULL,
    "turn_id" bigint,
    "content" "text" NOT NULL,
    "sort_order" integer DEFAULT 0 NOT NULL
);


ALTER TABLE "public"."feedback_items" OWNER TO "postgres";


ALTER TABLE "public"."feedback_items" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."feedback_items_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."miti_codes" (
    "id" bigint NOT NULL,
    "evaluation_id" bigint NOT NULL,
    "turn_id" bigint NOT NULL,
    "unit_no" integer DEFAULT 1 NOT NULL,
    "code" "public"."miti_code" NOT NULL,
    "excerpt" "text" NOT NULL,
    "reason" "text" NOT NULL,
    "uncertainty_note" "text",
    CONSTRAINT "miti_codes_unit_no_check" CHECK (("unit_no" > 0))
);


ALTER TABLE "public"."miti_codes" OWNER TO "postgres";


ALTER TABLE "public"."miti_codes" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."miti_codes_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."miti_globals" (
    "id" bigint NOT NULL,
    "evaluation_id" bigint NOT NULL,
    "dimension" "public"."global_dimension" NOT NULL,
    "score" smallint,
    "reason" "text" NOT NULL,
    "evidence_turn_nos" integer[] DEFAULT '{}'::integer[] NOT NULL,
    CONSTRAINT "miti_globals_score_check" CHECK ((("score" >= 1) AND ("score" <= 5)))
);


ALTER TABLE "public"."miti_globals" OWNER TO "postgres";


ALTER TABLE "public"."miti_globals" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."miti_globals_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."process_observations" (
    "id" bigint NOT NULL,
    "evaluation_id" bigint NOT NULL,
    "process" "public"."mi_process" NOT NULL,
    "start_turn_no" integer,
    "end_turn_no" integer,
    "excerpt" "text",
    "reason" "text" NOT NULL,
    CONSTRAINT "process_observations_check" CHECK ((("end_turn_no" IS NULL) OR ("start_turn_no" IS NULL) OR ("end_turn_no" >= "start_turn_no")))
);


ALTER TABLE "public"."process_observations" OWNER TO "postgres";


ALTER TABLE "public"."process_observations" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."process_observations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE SEQUENCE IF NOT EXISTS "public"."refresh_token_family_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE "public"."refresh_token_family_seq" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."refresh_tokens" (
    "id" bigint NOT NULL,
    "user_id" bigint NOT NULL,
    "family_id" bigint NOT NULL,
    "token_hash" "text" NOT NULL,
    "expires_at" timestamp with time zone NOT NULL,
    "revoked_at" timestamp with time zone,
    "replaced_by" bigint,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "refresh_tokens_check" CHECK (("expires_at" > "created_at"))
);


ALTER TABLE "public"."refresh_tokens" OWNER TO "postgres";


ALTER TABLE "public"."refresh_tokens" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."refresh_tokens_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."scenario_cases" (
    "scenario_id" bigint NOT NULL,
    "main_problem" "text" NOT NULL,
    "history_impact" "text",
    "expectation_change_context" "text" NOT NULL,
    "health_condition" "text",
    "initial_summary" "text"
);


ALTER TABLE "public"."scenario_cases" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."scenario_hidden_facts" (
    "id" bigint NOT NULL,
    "scenario_id" bigint NOT NULL,
    "code" "text" NOT NULL,
    "short_title" "text" NOT NULL,
    "fact" "text" NOT NULL,
    "sort_order" integer DEFAULT 0 NOT NULL,
    "min_disclosure_level" "public"."disclosure_level" DEFAULT 'medium'::"public"."disclosure_level" NOT NULL
);


ALTER TABLE "public"."scenario_hidden_facts" OWNER TO "postgres";


ALTER TABLE "public"."scenario_hidden_facts" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."scenario_hidden_facts_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."scenario_initial_states" (
    "scenario_id" bigint NOT NULL,
    "emotion_type" "text" NOT NULL,
    "emotion_cause" "text",
    "disclosure_level" "public"."disclosure_level" NOT NULL,
    "disclosure_trigger" "text",
    "reasons_to_change" "text",
    "reasons_to_maintain" "text",
    "ambivalence_lean" "public"."ambivalence_lean" NOT NULL,
    "discord_present" boolean DEFAULT false NOT NULL,
    "discord_context" "text",
    "discord_response" "text"
);


ALTER TABLE "public"."scenario_initial_states" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."scenario_personas" (
    "scenario_id" bigint NOT NULL,
    "name" "text" NOT NULL,
    "age" integer NOT NULL,
    "gender" "text" NOT NULL,
    "education" "text",
    "occupation" "text",
    "marital_status" "text",
    "family_background" "text",
    "personality" "text" NOT NULL,
    "communication_style" "text" NOT NULL,
    "additional_background" "text",
    CONSTRAINT "scenario_personas_age_check" CHECK ((("age" >= 10) AND ("age" <= 120)))
);


ALTER TABLE "public"."scenario_personas" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."scenarios" (
    "id" bigint NOT NULL,
    "title" "text" NOT NULL,
    "owner_id" bigint NOT NULL,
    "visibility" "public"."scenario_visibility" DEFAULT 'class'::"public"."scenario_visibility" NOT NULL,
    "review_status" "public"."review_status" DEFAULT 'draft'::"public"."review_status" NOT NULL,
    "change_target" "text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deleted_at" timestamp with time zone
);


ALTER TABLE "public"."scenarios" OWNER TO "postgres";


ALTER TABLE "public"."scenarios" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."scenarios_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."session_topics" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "sort_order" integer NOT NULL,
    "name" "text" NOT NULL,
    "source" "public"."topic_source" NOT NULL,
    "hidden_fact_code" "text",
    CONSTRAINT "session_topics_check" CHECK ((("source" = 'hidden_fact'::"public"."topic_source") = ("hidden_fact_code" IS NOT NULL)))
);


ALTER TABLE "public"."session_topics" OWNER TO "postgres";


ALTER TABLE "public"."session_topics" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."session_topics_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."sessions" (
    "id" bigint NOT NULL,
    "student_id" bigint NOT NULL,
    "scenario_id" bigint NOT NULL,
    "class_id" bigint,
    "parent_session_id" bigint,
    "scenario_snapshot" "jsonb" NOT NULL,
    "status" "public"."session_status" DEFAULT 'in_progress'::"public"."session_status" NOT NULL,
    "started_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "ended_at" timestamp with time zone,
    "duration_seconds" integer,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deleted_at" timestamp with time zone,
    CONSTRAINT "sessions_check" CHECK ((("ended_at" IS NULL) OR ("ended_at" >= "started_at"))),
    CONSTRAINT "sessions_check1" CHECK ((("parent_session_id" IS NULL) OR ("parent_session_id" <> "id"))),
    CONSTRAINT "sessions_duration_seconds_check" CHECK (("duration_seconds" >= 0))
);


ALTER TABLE "public"."sessions" OWNER TO "postgres";


ALTER TABLE "public"."sessions" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."sessions_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."topic_notes_log" (
    "id" bigint NOT NULL,
    "session_topic_id" bigint NOT NULL,
    "turn_id" bigint,
    "description" "text" DEFAULT ''::"text" NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL
);


ALTER TABLE "public"."topic_notes_log" OWNER TO "postgres";


ALTER TABLE "public"."topic_notes_log" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."topic_notes_log_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."turns" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "turn_no" integer NOT NULL,
    "speaker" "public"."speaker" NOT NULL,
    "content" "text" NOT NULL,
    "start_ms" integer NOT NULL,
    "end_ms" integer NOT NULL,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    CONSTRAINT "turns_check" CHECK (("end_ms" >= "start_ms")),
    CONSTRAINT "turns_start_ms_check" CHECK (("start_ms" >= 0)),
    CONSTRAINT "turns_turn_no_check" CHECK (("turn_no" > 0))
);


ALTER TABLE "public"."turns" OWNER TO "postgres";


ALTER TABLE "public"."turns" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."turns_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."users" (
    "id" bigint NOT NULL,
    "name" "text" NOT NULL,
    "email" "text" NOT NULL,
    "password_hash" "text",
    "role" "public"."user_role" NOT NULL,
    "activation_token_hash" "text",
    "activation_token_expires_at" timestamp with time zone,
    "activated_at" timestamp with time zone,
    "created_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "updated_at" timestamp with time zone DEFAULT "now"() NOT NULL,
    "deleted_at" timestamp with time zone
);


ALTER TABLE "public"."users" OWNER TO "postgres";


ALTER TABLE "public"."users" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."users_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE OR REPLACE VIEW "public"."v_code_counts" AS
 SELECT "evaluation_id",
    "code",
    "count"(*) AS "total"
   FROM "public"."miti_codes"
  GROUP BY "evaluation_id", "code";


ALTER VIEW "public"."v_code_counts" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_sessions_for_lecturer" AS
 SELECT "s"."id",
    "s"."student_id",
    "s"."scenario_id",
    "s"."class_id",
    "s"."parent_session_id",
    "s"."scenario_snapshot",
    "s"."status",
    "s"."started_at",
    "s"."ended_at",
    "s"."duration_seconds",
    "s"."created_at",
    "s"."updated_at",
    "s"."deleted_at",
    "u"."id" AS "lecturer_id"
   FROM (("public"."sessions" "s"
     JOIN "public"."class_members" "cm" ON ((("cm"."class_id" = "s"."class_id") AND ("cm"."deleted_at" IS NULL))))
     JOIN "public"."users" "u" ON ((("u"."id" = "cm"."user_id") AND ("u"."role" = 'lecturer'::"public"."user_role") AND ("u"."deleted_at" IS NULL))))
  WHERE (("s"."class_id" IS NOT NULL) AND ("s"."deleted_at" IS NULL));


ALTER VIEW "public"."v_sessions_for_lecturer" OWNER TO "postgres";


CREATE OR REPLACE VIEW "public"."v_summary_measures" AS
 WITH "c" AS (
         SELECT "miti_codes"."evaluation_id",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'Q'::"public"."miti_code")) AS "q",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'SR'::"public"."miti_code")) AS "sr",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'CR'::"public"."miti_code")) AS "cr",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'AF'::"public"."miti_code")) AS "af",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'SEEK'::"public"."miti_code")) AS "seek",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'EA'::"public"."miti_code")) AS "ea",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'P'::"public"."miti_code")) AS "p",
            "count"(*) FILTER (WHERE ("miti_codes"."code" = 'CONFRONT'::"public"."miti_code")) AS "confront"
           FROM "public"."miti_codes"
          GROUP BY "miti_codes"."evaluation_id"
        )
 SELECT "e"."id" AS "evaluation_id",
    "round"(((100.0 * ("c"."cr")::numeric) / (NULLIF(("c"."sr" + "c"."cr"), 0))::numeric), 2) AS "pct_cr",
    "round"(((("c"."sr" + "c"."cr"))::numeric / (NULLIF("c"."q", 0))::numeric), 2) AS "reflection_question_ratio",
    (("c"."af" + "c"."seek") + "c"."ea") AS "total_mia",
    ("c"."p" + "c"."confront") AS "total_mina",
    ( SELECT "avg"("g"."score") AS "avg"
           FROM "public"."miti_globals" "g"
          WHERE (("g"."evaluation_id" = "e"."id") AND ("g"."dimension" = ANY (ARRAY['cultivating_change_talk'::"public"."global_dimension", 'softening_sustain_talk'::"public"."global_dimension"])))) AS "technical_global",
    ( SELECT "avg"("g"."score") AS "avg"
           FROM "public"."miti_globals" "g"
          WHERE (("g"."evaluation_id" = "e"."id") AND ("g"."dimension" = ANY (ARRAY['partnership'::"public"."global_dimension", 'empathy'::"public"."global_dimension"])))) AS "relational_global"
   FROM ("public"."evaluations" "e"
     LEFT JOIN "c" ON (("c"."evaluation_id" = "e"."id")));


ALTER VIEW "public"."v_summary_measures" OWNER TO "postgres";


CREATE TABLE IF NOT EXISTS "public"."vocal_observations" (
    "id" bigint NOT NULL,
    "session_id" bigint NOT NULL,
    "turn_id" bigint NOT NULL,
    "speaking_rate" numeric(6,3),
    "mean_pitch" numeric(8,3),
    "mean_energy" numeric(10,5),
    "rate_ratio" numeric(6,3),
    "pitch_ratio" numeric(6,3),
    "energy_ratio" numeric(6,3),
    "usable" boolean DEFAULT true NOT NULL,
    "note" "text",
    CONSTRAINT "vocal_observations_mean_energy_check" CHECK (("mean_energy" >= (0)::numeric)),
    CONSTRAINT "vocal_observations_mean_pitch_check" CHECK (("mean_pitch" >= (0)::numeric)),
    CONSTRAINT "vocal_observations_speaking_rate_check" CHECK (("speaking_rate" >= (0)::numeric))
);


ALTER TABLE "public"."vocal_observations" OWNER TO "postgres";


ALTER TABLE "public"."vocal_observations" ALTER COLUMN "id" ADD GENERATED ALWAYS AS IDENTITY (
    SEQUENCE NAME "public"."vocal_observations_id_seq"
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1
);



CREATE TABLE IF NOT EXISTS "public"."vocal_session_averages" (
    "session_id" bigint NOT NULL,
    "speaking_rate" numeric(6,3),
    "mean_pitch" numeric(8,3),
    "mean_energy" numeric(10,5)
);


ALTER TABLE "public"."vocal_session_averages" OWNER TO "postgres";


ALTER TABLE ONLY "public"."class_members"
    ADD CONSTRAINT "class_members_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."class_scenarios"
    ADD CONSTRAINT "class_scenarios_class_id_scenario_id_key" UNIQUE ("class_id", "scenario_id");



ALTER TABLE ONLY "public"."class_scenarios"
    ADD CONSTRAINT "class_scenarios_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."classes"
    ADD CONSTRAINT "classes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."client_state_log"
    ADD CONSTRAINT "client_state_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."consents"
    ADD CONSTRAINT "consents_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."evaluations"
    ADD CONSTRAINT "evaluations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."evaluations"
    ADD CONSTRAINT "evaluations_session_id_key" UNIQUE ("session_id");



ALTER TABLE ONLY "public"."face_observations"
    ADD CONSTRAINT "face_observations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."feedback_items"
    ADD CONSTRAINT "feedback_items_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."miti_codes"
    ADD CONSTRAINT "miti_codes_evaluation_id_turn_id_code_key" UNIQUE ("evaluation_id", "turn_id", "code");



ALTER TABLE ONLY "public"."miti_codes"
    ADD CONSTRAINT "miti_codes_evaluation_id_turn_id_unit_no_key" UNIQUE ("evaluation_id", "turn_id", "unit_no");



ALTER TABLE ONLY "public"."miti_codes"
    ADD CONSTRAINT "miti_codes_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."miti_globals"
    ADD CONSTRAINT "miti_globals_evaluation_id_dimension_key" UNIQUE ("evaluation_id", "dimension");



ALTER TABLE ONLY "public"."miti_globals"
    ADD CONSTRAINT "miti_globals_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."process_observations"
    ADD CONSTRAINT "process_observations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."refresh_tokens"
    ADD CONSTRAINT "refresh_tokens_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."refresh_tokens"
    ADD CONSTRAINT "refresh_tokens_token_hash_key" UNIQUE ("token_hash");



ALTER TABLE ONLY "public"."scenario_cases"
    ADD CONSTRAINT "scenario_cases_pkey" PRIMARY KEY ("scenario_id");



ALTER TABLE ONLY "public"."scenario_hidden_facts"
    ADD CONSTRAINT "scenario_hidden_facts_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."scenario_hidden_facts"
    ADD CONSTRAINT "scenario_hidden_facts_scenario_id_code_key" UNIQUE ("scenario_id", "code");



ALTER TABLE ONLY "public"."scenario_initial_states"
    ADD CONSTRAINT "scenario_initial_states_pkey" PRIMARY KEY ("scenario_id");



ALTER TABLE ONLY "public"."scenario_personas"
    ADD CONSTRAINT "scenario_personas_pkey" PRIMARY KEY ("scenario_id");



ALTER TABLE ONLY "public"."scenarios"
    ADD CONSTRAINT "scenarios_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."session_topics"
    ADD CONSTRAINT "session_topics_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."session_topics"
    ADD CONSTRAINT "session_topics_session_id_name_key" UNIQUE ("session_id", "name");



ALTER TABLE ONLY "public"."session_topics"
    ADD CONSTRAINT "session_topics_session_id_sort_order_key" UNIQUE ("session_id", "sort_order");



ALTER TABLE ONLY "public"."sessions"
    ADD CONSTRAINT "sessions_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."topic_notes_log"
    ADD CONSTRAINT "topic_notes_log_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."turns"
    ADD CONSTRAINT "turns_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."turns"
    ADD CONSTRAINT "turns_session_id_turn_no_key" UNIQUE ("session_id", "turn_no");



ALTER TABLE ONLY "public"."users"
    ADD CONSTRAINT "users_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."vocal_observations"
    ADD CONSTRAINT "vocal_observations_pkey" PRIMARY KEY ("id");



ALTER TABLE ONLY "public"."vocal_observations"
    ADD CONSTRAINT "vocal_observations_turn_id_key" UNIQUE ("turn_id");



ALTER TABLE ONLY "public"."vocal_session_averages"
    ADD CONSTRAINT "vocal_session_averages_pkey" PRIMARY KEY ("session_id");



CREATE INDEX "ix_class_members_user" ON "public"."class_members" USING "btree" ("user_id") WHERE ("deleted_at" IS NULL);



CREATE INDEX "ix_consents_user" ON "public"."consents" USING "btree" ("user_id", "kind", "recorded_at" DESC);



CREATE INDEX "ix_face_observations_session" ON "public"."face_observations" USING "btree" ("session_id", "time_ms");



CREATE INDEX "ix_feedback_items_evaluation" ON "public"."feedback_items" USING "btree" ("evaluation_id", "kind", "sort_order");



CREATE INDEX "ix_miti_codes_evaluation" ON "public"."miti_codes" USING "btree" ("evaluation_id", "code");



CREATE INDEX "ix_process_observations_evaluation" ON "public"."process_observations" USING "btree" ("evaluation_id");



CREATE INDEX "ix_refresh_tokens_family" ON "public"."refresh_tokens" USING "btree" ("family_id");



CREATE INDEX "ix_refresh_tokens_user" ON "public"."refresh_tokens" USING "btree" ("user_id") WHERE ("revoked_at" IS NULL);



CREATE INDEX "ix_scenarios_catalog" ON "public"."scenarios" USING "btree" ("visibility", "review_status") WHERE ("deleted_at" IS NULL);



CREATE INDEX "ix_scenarios_owner" ON "public"."scenarios" USING "btree" ("owner_id") WHERE ("deleted_at" IS NULL);



CREATE INDEX "ix_sessions_class" ON "public"."sessions" USING "btree" ("class_id", "started_at" DESC) WHERE (("deleted_at" IS NULL) AND ("class_id" IS NOT NULL));



CREATE INDEX "ix_sessions_parent" ON "public"."sessions" USING "btree" ("parent_session_id") WHERE ("parent_session_id" IS NOT NULL);



CREATE INDEX "ix_sessions_student" ON "public"."sessions" USING "btree" ("student_id", "started_at" DESC) WHERE ("deleted_at" IS NULL);



CREATE INDEX "ix_vocal_observations_session" ON "public"."vocal_observations" USING "btree" ("session_id");



CREATE UNIQUE INDEX "uq_class_members_active" ON "public"."class_members" USING "btree" ("class_id", "user_id") WHERE ("deleted_at" IS NULL);



CREATE UNIQUE INDEX "uq_classes_name_year_active" ON "public"."classes" USING "btree" ("name", "academic_year") WHERE ("deleted_at" IS NULL);



CREATE UNIQUE INDEX "uq_client_state_initial" ON "public"."client_state_log" USING "btree" ("session_id") WHERE ("turn_id" IS NULL);



CREATE UNIQUE INDEX "uq_client_state_turn" ON "public"."client_state_log" USING "btree" ("session_id", "turn_id") WHERE ("turn_id" IS NOT NULL);



CREATE UNIQUE INDEX "uq_topic_notes_initial" ON "public"."topic_notes_log" USING "btree" ("session_topic_id") WHERE ("turn_id" IS NULL);



CREATE UNIQUE INDEX "uq_topic_notes_turn" ON "public"."topic_notes_log" USING "btree" ("session_topic_id", "turn_id") WHERE ("turn_id" IS NOT NULL);



CREATE UNIQUE INDEX "uq_users_email_active" ON "public"."users" USING "btree" ("lower"("email")) WHERE ("deleted_at" IS NULL);



CREATE OR REPLACE TRIGGER "trg_classes_updated" BEFORE UPDATE ON "public"."classes" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_evaluations_updated" BEFORE UPDATE ON "public"."evaluations" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_miti_codes_rules" BEFORE INSERT OR UPDATE ON "public"."miti_codes" FOR EACH ROW EXECUTE FUNCTION "public"."check_miti_rules"();



CREATE OR REPLACE TRIGGER "trg_scenarios_updated" BEFORE UPDATE ON "public"."scenarios" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_sessions_updated" BEFORE UPDATE ON "public"."sessions" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



CREATE OR REPLACE TRIGGER "trg_users_updated" BEFORE UPDATE ON "public"."users" FOR EACH ROW EXECUTE FUNCTION "public"."set_updated_at"();



ALTER TABLE ONLY "public"."class_members"
    ADD CONSTRAINT "class_members_class_id_fkey" FOREIGN KEY ("class_id") REFERENCES "public"."classes"("id");



ALTER TABLE ONLY "public"."class_members"
    ADD CONSTRAINT "class_members_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."class_scenarios"
    ADD CONSTRAINT "class_scenarios_assigned_by_fkey" FOREIGN KEY ("assigned_by") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."class_scenarios"
    ADD CONSTRAINT "class_scenarios_class_id_fkey" FOREIGN KEY ("class_id") REFERENCES "public"."classes"("id");



ALTER TABLE ONLY "public"."class_scenarios"
    ADD CONSTRAINT "class_scenarios_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id");



ALTER TABLE ONLY "public"."client_state_log"
    ADD CONSTRAINT "client_state_log_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."client_state_log"
    ADD CONSTRAINT "client_state_log_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."consents"
    ADD CONSTRAINT "consents_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."evaluations"
    ADD CONSTRAINT "evaluations_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."face_observations"
    ADD CONSTRAINT "face_observations_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."face_observations"
    ADD CONSTRAINT "face_observations_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE SET NULL;



ALTER TABLE ONLY "public"."feedback_items"
    ADD CONSTRAINT "feedback_items_evaluation_id_fkey" FOREIGN KEY ("evaluation_id") REFERENCES "public"."evaluations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."feedback_items"
    ADD CONSTRAINT "feedback_items_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."miti_codes"
    ADD CONSTRAINT "miti_codes_evaluation_id_fkey" FOREIGN KEY ("evaluation_id") REFERENCES "public"."evaluations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."miti_codes"
    ADD CONSTRAINT "miti_codes_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."miti_globals"
    ADD CONSTRAINT "miti_globals_evaluation_id_fkey" FOREIGN KEY ("evaluation_id") REFERENCES "public"."evaluations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."process_observations"
    ADD CONSTRAINT "process_observations_evaluation_id_fkey" FOREIGN KEY ("evaluation_id") REFERENCES "public"."evaluations"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."refresh_tokens"
    ADD CONSTRAINT "refresh_tokens_replaced_by_fkey" FOREIGN KEY ("replaced_by") REFERENCES "public"."refresh_tokens"("id");



ALTER TABLE ONLY "public"."refresh_tokens"
    ADD CONSTRAINT "refresh_tokens_user_id_fkey" FOREIGN KEY ("user_id") REFERENCES "public"."users"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."scenario_cases"
    ADD CONSTRAINT "scenario_cases_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."scenario_hidden_facts"
    ADD CONSTRAINT "scenario_hidden_facts_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."scenario_initial_states"
    ADD CONSTRAINT "scenario_initial_states_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."scenario_personas"
    ADD CONSTRAINT "scenario_personas_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."scenarios"
    ADD CONSTRAINT "scenarios_owner_id_fkey" FOREIGN KEY ("owner_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."session_topics"
    ADD CONSTRAINT "session_topics_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."sessions"
    ADD CONSTRAINT "sessions_class_id_fkey" FOREIGN KEY ("class_id") REFERENCES "public"."classes"("id");



ALTER TABLE ONLY "public"."sessions"
    ADD CONSTRAINT "sessions_parent_session_id_fkey" FOREIGN KEY ("parent_session_id") REFERENCES "public"."sessions"("id");



ALTER TABLE ONLY "public"."sessions"
    ADD CONSTRAINT "sessions_scenario_id_fkey" FOREIGN KEY ("scenario_id") REFERENCES "public"."scenarios"("id");



ALTER TABLE ONLY "public"."sessions"
    ADD CONSTRAINT "sessions_student_id_fkey" FOREIGN KEY ("student_id") REFERENCES "public"."users"("id");



ALTER TABLE ONLY "public"."topic_notes_log"
    ADD CONSTRAINT "topic_notes_log_session_topic_id_fkey" FOREIGN KEY ("session_topic_id") REFERENCES "public"."session_topics"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."topic_notes_log"
    ADD CONSTRAINT "topic_notes_log_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."turns"
    ADD CONSTRAINT "turns_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."vocal_observations"
    ADD CONSTRAINT "vocal_observations_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."vocal_observations"
    ADD CONSTRAINT "vocal_observations_turn_id_fkey" FOREIGN KEY ("turn_id") REFERENCES "public"."turns"("id") ON DELETE CASCADE;



ALTER TABLE ONLY "public"."vocal_session_averages"
    ADD CONSTRAINT "vocal_session_averages_session_id_fkey" FOREIGN KEY ("session_id") REFERENCES "public"."sessions"("id") ON DELETE CASCADE;



ALTER TABLE "public"."class_members" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."class_scenarios" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."classes" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."client_state_log" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."consents" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."evaluations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."face_observations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."feedback_items" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."miti_codes" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."miti_globals" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."process_observations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."refresh_tokens" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scenario_cases" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scenario_hidden_facts" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scenario_initial_states" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scenario_personas" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."scenarios" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."session_topics" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."sessions" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."topic_notes_log" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."turns" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."users" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."vocal_observations" ENABLE ROW LEVEL SECURITY;


ALTER TABLE "public"."vocal_session_averages" ENABLE ROW LEVEL SECURITY;




ALTER PUBLICATION "supabase_realtime" OWNER TO "postgres";


GRANT USAGE ON SCHEMA "public" TO "postgres";
GRANT USAGE ON SCHEMA "public" TO "anon";
GRANT USAGE ON SCHEMA "public" TO "authenticated";
GRANT USAGE ON SCHEMA "public" TO "service_role";

























































































































































REVOKE ALL ON FUNCTION "public"."build_scenario_snapshot"("p_scenario_id" bigint) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."build_scenario_snapshot"("p_scenario_id" bigint) TO "service_role";



GRANT ALL ON FUNCTION "public"."check_miti_rules"() TO "anon";
GRANT ALL ON FUNCTION "public"."check_miti_rules"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."check_miti_rules"() TO "service_role";



REVOKE ALL ON FUNCTION "public"."purge_deleted_sessions"("days" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."purge_deleted_sessions"("days" integer) TO "service_role";



REVOKE ALL ON FUNCTION "public"."purge_old_refresh_tokens"("days" integer) FROM PUBLIC;
GRANT ALL ON FUNCTION "public"."purge_old_refresh_tokens"("days" integer) TO "service_role";



GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "anon";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "authenticated";
GRANT ALL ON FUNCTION "public"."set_updated_at"() TO "service_role";


















GRANT ALL ON TABLE "public"."class_members" TO "service_role";



GRANT ALL ON SEQUENCE "public"."class_members_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."class_scenarios" TO "service_role";



GRANT ALL ON SEQUENCE "public"."class_scenarios_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."classes" TO "service_role";



GRANT ALL ON SEQUENCE "public"."classes_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."client_state_log" TO "service_role";



GRANT ALL ON SEQUENCE "public"."client_state_log_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."consents" TO "service_role";



GRANT ALL ON SEQUENCE "public"."consents_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."evaluations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."evaluations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."face_observations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."face_observations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."feedback_items" TO "service_role";



GRANT ALL ON SEQUENCE "public"."feedback_items_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."miti_codes" TO "service_role";



GRANT ALL ON SEQUENCE "public"."miti_codes_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."miti_globals" TO "service_role";



GRANT ALL ON SEQUENCE "public"."miti_globals_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."process_observations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."process_observations_id_seq" TO "service_role";



GRANT ALL ON SEQUENCE "public"."refresh_token_family_seq" TO "service_role";



GRANT ALL ON TABLE "public"."refresh_tokens" TO "service_role";



GRANT ALL ON SEQUENCE "public"."refresh_tokens_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."scenario_cases" TO "service_role";



GRANT ALL ON TABLE "public"."scenario_hidden_facts" TO "service_role";



GRANT ALL ON SEQUENCE "public"."scenario_hidden_facts_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."scenario_initial_states" TO "service_role";



GRANT ALL ON TABLE "public"."scenario_personas" TO "service_role";



GRANT ALL ON TABLE "public"."scenarios" TO "service_role";



GRANT ALL ON SEQUENCE "public"."scenarios_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."session_topics" TO "service_role";



GRANT ALL ON SEQUENCE "public"."session_topics_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."sessions" TO "service_role";



GRANT ALL ON SEQUENCE "public"."sessions_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."topic_notes_log" TO "service_role";



GRANT ALL ON SEQUENCE "public"."topic_notes_log_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."turns" TO "service_role";



GRANT ALL ON SEQUENCE "public"."turns_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."users" TO "service_role";



GRANT ALL ON SEQUENCE "public"."users_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."v_code_counts" TO "service_role";



GRANT ALL ON TABLE "public"."v_sessions_for_lecturer" TO "service_role";



GRANT ALL ON TABLE "public"."v_summary_measures" TO "service_role";



GRANT ALL ON TABLE "public"."vocal_observations" TO "service_role";



GRANT ALL ON SEQUENCE "public"."vocal_observations_id_seq" TO "service_role";



GRANT ALL ON TABLE "public"."vocal_session_averages" TO "service_role";









ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON SEQUENCES TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON FUNCTIONS TO "service_role";






ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "postgres";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "anon";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "authenticated";
ALTER DEFAULT PRIVILEGES FOR ROLE "postgres" IN SCHEMA "public" GRANT ALL ON TABLES TO "service_role";
































RESET search_path;
