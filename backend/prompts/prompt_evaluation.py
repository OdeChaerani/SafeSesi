"""Prompt agen evaluator MITI (Behavior Coding, Global Scoring, Process Observation, Feedback).

Referensi kurasi ada di prompts/miti/*.md. Prompt evaluator hanya menerima transkrip, target
perubahan, dan ringkasan publik skenario: persona, hidden facts, dan Client State tidak pernah
dikirim (Rubrik 3.2: informasi yang belum diungkap klien tidak dipakai menilai mahasiswa).
"""
from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any

MITI_DIR = Path(__file__).resolve().parent / "miti"

LANGUAGE_RULES = (
    "The transcript may be in Indonesian or English. Copy every excerpt verbatim in the transcript's own "
    "language. Write every reason, explanation and observation in Indonesian (Bahasa Indonesia), in plain "
    "words a psychology student can follow."
)


@lru_cache(maxsize=None)
def reference(name: str) -> str:
    return (MITI_DIR / f"{name}.md").read_text(encoding="utf-8")


def format_transcript(turns: list[dict[str, Any]]) -> str:
    """Transkrip bernomor giliran: '[T3] COUNSELOR: ...'. Nomor = turn_no di database/fixture."""
    lines = []
    for t in turns:
        who = "COUNSELOR" if t["speaker"] == "counselor" else "CLIENT"
        lines.append(f"[T{t['turn_no']}] {who}: {t['content']}")
    return "\n".join(lines)


def session_context(change_target: str, initial_summary: str | None) -> str:
    ctx = f"Designated change goal (target behavior): {change_target}"
    if initial_summary:
        ctx += f"\nPublic scenario summary shown to the student: {initial_summary}"
    return ctx


# --- Behavior Coding Agent --------------------------------------------------------------

BEHAVIOR_CODING_SYSTEM = f"""You are an experienced MITI 4.2.1 coder. Code every counselor turn of the transcript
using ONLY the reference below.

{{reference}}

Task:
- Return exactly one entry per COUNSELOR turn, using the bracketed turn number as turn_no. Never code
  client turns.
- For each counselor turn, first write volley_reason, then continues_previous_volley (E.3): true only
  when the client turn right before it was purely facilitative and did not answer a direct question or
  respond to a reflection. The first counselor turn is always false.
- Split the turn into units (complete thoughts). For each unit write the reason BEFORE the code.
- code: the main code or null. alternative_code: a second candidate you seriously considered, else
  null. certain: true only if you are confident. Do not apply volley counting limits yourself
  (one Q / one reflection / one persuasion per volley); deterministic rules do that afterwards.
- same_affirmation_as_turn: for an AF unit that repeats an affirmation already given earlier, the
  earlier counselor turn number; otherwise null.
- Use the client's surrounding turns as context (what was just said, whether permission was given,
  tone cues in the words). Voice tone is not available: note this in uncertainty_note when it matters.
- {LANGUAGE_RULES}
"""


def behavior_coding_prompts(turns: list[dict[str, Any]], change_target: str, initial_summary: str | None) -> tuple[str, str]:
    system = BEHAVIOR_CODING_SYSTEM.replace("{reference}", reference("behavior_codes"))
    user = f"{session_context(change_target, initial_summary)}\n\nTranscript:\n{format_transcript(turns)}"
    return system, user


# --- Global Scoring Agent ---------------------------------------------------------------

GLOBAL_SCORING_SYSTEM = f"""You are an experienced MITI 4.2.1 rater. Rate the four global dimensions for the whole
transcript using ONLY the reference below.

{{reference}}

Task:
- For each dimension write the reason first (evidence that supports AND limits the score), then
  evidence_turn_nos (bracketed turn numbers), then the integer score 1–5.
- Rate the session as a whole relative to the designated change goal.
- {LANGUAGE_RULES}
"""


def global_scoring_prompts(turns: list[dict[str, Any]], change_target: str, initial_summary: str | None) -> tuple[str, str]:
    system = GLOBAL_SCORING_SYSTEM.replace("{reference}", reference("global_scores"))
    user = f"{session_context(change_target, initial_summary)}\n\nTranscript:\n{format_transcript(turns)}"
    return system, user


# --- Process Observation Agent ----------------------------------------------------------

PROCESS_OBSERVATION_SYSTEM = f"""You observe which motivational interviewing processes are visible in a counseling
transcript, using ONLY the guide below. You do not score.

{{reference}}

Task:
- Report all four processes (engaging, focusing, evoking, planning). A process may appear in several
  separate stretches; report one item per stretch.
- For each item write the reason first, then evidence_found, then start_turn_no/end_turn_no (bracketed
  numbers, counselor and client turns both allowed) and a verbatim excerpt of the counselor turn (and
  the client response if relevant).
- If there is not enough evidence for a process, return a single item for it with evidence_found=false,
  null turns and null excerpt, and say in the reason what is missing.
- {LANGUAGE_RULES}
"""


def process_observation_prompts(turns: list[dict[str, Any]], change_target: str, initial_summary: str | None) -> tuple[str, str]:
    system = PROCESS_OBSERVATION_SYSTEM.replace("{reference}", reference("mi_processes"))
    user = f"{session_context(change_target, initial_summary)}\n\nTranscript:\n{format_transcript(turns)}"
    return system, user


# --- Feedback Agent ---------------------------------------------------------------------

FEEDBACK_SYSTEM = f"""You write learning feedback for a psychology student who played the counselor in a
motivational interviewing practice session. Rules (Rubrik SafeSesi 3.2):
- Give strengths (kind "strength"), development areas (kind "improvement"), and alternative responses
  (kind "alternative_response"). Base every item on evidence; do not force a fixed number of items when
  evidence is limited.
- Every item points to one turn (turn_no) and quotes it verbatim in excerpt (copy the words exactly
  from that turn). Use evidence_turn_nos for other relevant turns, e.g. the client's response.
- An alternative_response is tied to a specific counselor turn and gives, in alternative_text, a
  concrete sentence the student could say at that moment, in the transcript's language. It is one
  possible option, not the only correct answer. Its explanation says why it may help.
- Link explanations to MITI codes or global ratings where useful, explaining terms simply.
- Information the client never disclosed in the transcript must not be used to blame the student.
- Do not add numbers, totals, pass/fail judgments or conclusions not supported by the transcript.
- {LANGUAGE_RULES}
"""


def feedback_prompts(
    turns: list[dict[str, Any]],
    change_target: str,
    initial_summary: str | None,
    coded_turns: list[dict[str, Any]],
    globals_: dict[str, Any] | None,
    processes: list[dict[str, Any]] | None,
    correction: str | None = None,
) -> tuple[str, str]:
    payload: dict[str, Any] = {"behavior_codes_per_turn": coded_turns}
    if globals_:
        payload["global_ratings"] = globals_
    if processes:
        payload["mi_process_observations"] = processes
    user = (
        f"{session_context(change_target, initial_summary)}\n\nTranscript:\n{format_transcript(turns)}\n\n"
        f"Evaluation results (JSON):\n{json.dumps(payload, ensure_ascii=False)}"
    )
    if correction:
        user += f"\n\nYour previous answer had invalid items. Fix them:\n{correction}"
    return FEEDBACK_SYSTEM, user
