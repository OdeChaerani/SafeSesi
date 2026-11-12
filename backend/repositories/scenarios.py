from __future__ import annotations

import json
from typing import Any
import asyncpg

from schemas.scenario import DEFAULT_MIN_DISCLOSURE_LEVEL


async def get_scenario_by_id(conn: asyncpg.Connection, scenario_id: int) -> dict[str, Any] | None:
    """Mengambil metadata skenario yang belum dihapus."""
    row = await conn.fetchrow(
        """
        SELECT id, title, owner_id, visibility, review_status, change_target, created_at, updated_at
        FROM scenarios
        WHERE id = $1 AND deleted_at IS NULL
        """,
        scenario_id,
    )
    return dict(row) if row else None


async def build_scenario_snapshot(conn: asyncpg.Connection, scenario_id: int) -> dict[str, Any] | None:
    """Memanggil fungsi SQL build_scenario_snapshot(:scenario_id) untuk menghasilkan snapshot JSONB.

    Fungsi SQL memakai to_jsonb(baris), sehingga scenario_hidden_facts.min_disclosure_level
    dan scenario_cases.initial_summary ikut terbawa otomatis. Default di bawah hanya
    jaring pengaman bila kolom belum ada di database.
    """
    val = await conn.fetchval(
        "SELECT build_scenario_snapshot($1)",
        scenario_id,
    )
    if not val:
        return None
    snapshot = json.loads(val) if isinstance(val, str) else dict(val)

    for fact in snapshot.get("hidden_facts") or []:
        fact.setdefault("min_disclosure_level", DEFAULT_MIN_DISCLOSURE_LEVEL)
    if isinstance(snapshot.get("case"), dict):
        snapshot["case"].setdefault("initial_summary", None)
    return snapshot


async def validate_catalog_access(conn: asyncpg.Connection, scenario_id: int) -> bool:
    """Validasi apakah skenario tersedia di katalog umum untuk latihan mandiri."""
    row = await conn.fetchrow(
        """
        SELECT 1 FROM scenarios
        WHERE id = $1 AND visibility = 'catalog' AND deleted_at IS NULL
        """,
        scenario_id,
    )
    return row is not None


async def get_catalog_scenarios(
    conn: asyncpg.Connection,
    student_id: int,
    search: str | None = None,
    status_filter: str = "all",
) -> dict[str, Any]:
    """Mengambil katalog skenario latihan mandiri beserta status latihan mahasiswa."""
    clean_search = search.strip() if search and search.strip() else None

    # 1. Ambil seluruh data katalog dasar untuk mahasiswa ini (termasuk status)
    rows = await conn.fetch(
        """
        WITH scenario_stats AS (
            SELECT 
                sc.id,
                sc.title,
                sc.change_target,
                p.name AS client_name,
                p.age AS client_age,
                p.gender AS client_gender,
                COALESCE(NULLIF(p.occupation, ''), NULLIF(p.education, ''), 'Klien Virtual') AS client_role,
                c.initial_summary,
                COUNT(se.id) AS total_attempts,
                CASE WHEN COUNT(se.id) > 0 THEN 'attempted' ELSE 'unattempted' END AS attempt_status,
                MAX(se.id) FILTER (WHERE se.status = 'completed') AS last_completed_session_id,
                MAX(se.id) FILTER (WHERE se.status = 'in_progress') AS active_session_id
            FROM scenarios sc
            JOIN scenario_personas p ON p.scenario_id = sc.id
            JOIN scenario_cases c ON c.scenario_id = sc.id
            LEFT JOIN sessions se ON se.scenario_id = sc.id AND se.student_id = $1
            WHERE sc.visibility = 'catalog' AND sc.deleted_at IS NULL
            GROUP BY sc.id, p.name, p.age, p.gender, p.occupation, p.education, c.initial_summary
            ORDER BY sc.id ASC
        )
        SELECT * FROM scenario_stats
        """,
        student_id,
    )

    all_items = [dict(r) for r in rows]
    total_count = len(all_items)
    unattempted_count = sum(1 for item in all_items if item["attempt_status"] == "unattempted")
    attempted_count = sum(1 for item in all_items if item["attempt_status"] == "attempted")

    # 2. Filter berdasarkan search & status jika diminta
    filtered_items = all_items
    if clean_search:
        search_lower = clean_search.lower()
        filtered_items = [
            item for item in filtered_items
            if search_lower in item["title"].lower()
            or search_lower in item["client_name"].lower()
            or search_lower in (item["initial_summary"] or "").lower()
            or search_lower in item["change_target"].lower()
        ]

    if status_filter in ("unattempted", "attempted"):
        filtered_items = [
            item for item in filtered_items
            if item["attempt_status"] == status_filter
        ]

    return {
        "items": filtered_items,
        "total": total_count,
        "unattempted_count": unattempted_count,
        "attempted_count": attempted_count,
    }


async def validate_class_access(
    conn: asyncpg.Connection, scenario_id: int, class_id: int, student_id: int
) -> bool:
    """Validasi apakah skenario ditugaskan pada kelas dan mahasiswa terdaftar di kelas tersebut."""
    row = await conn.fetchrow(
        """
        SELECT 1
        FROM class_scenarios cs
        JOIN class_members cm ON cm.class_id = cs.class_id
        JOIN classes cl ON cl.id = cs.class_id
        JOIN scenarios sc ON sc.id = cs.scenario_id
        WHERE cs.scenario_id = $1
          AND cs.class_id = $2
          AND cm.user_id = $3
          AND cl.deleted_at IS NULL
          AND sc.deleted_at IS NULL
        """,
        scenario_id,
        class_id,
        student_id,
    )
    return row is not None

