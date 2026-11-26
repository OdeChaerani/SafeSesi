from __future__ import annotations

from typing import Any, Literal
import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query, status

from api.deps import get_db, require_role
from repositories.scenarios import fetch_public_scenarios, get_catalog_scenarios, validate_class_access
from schemas.scenario import CatalogScenarioItem, CatalogScenarioResponse

router = APIRouter(prefix="/scenarios", tags=["scenarios"])


@router.get("/catalog", response_model=CatalogScenarioResponse)
async def list_catalog_scenarios(
    search: str | None = Query(
        default=None, description="Pencarian judul atau kata kunci skenario"
    ),
    status: Literal["all", "unattempted", "attempted"] = Query(
        default="all",
        description="Filter status latihan: all | unattempted | attempted",
    ),
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Mengambil daftar skenario latihan mandiri (katalog umum) beserta status pengerjaan mahasiswa."""
    return await get_catalog_scenarios(
        conn=conn,
        student_id=user["id"],
        search=search,
        status_filter=status,
    )


@router.get("/{scenario_id}", response_model=CatalogScenarioItem)
async def get_scenario_briefing(
    scenario_id: int,
    class_id: int | None = Query(default=None, description="ID kelas bila skenario dibuka dari kelas"),
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Ringkasan publik satu skenario untuk halaman briefing.

    Hanya judul, target perubahan, identitas dasar klien, dan ringkasan awal (+ status percobaan
    mahasiswa). Persona lengkap, isi kasus, dan fakta tersembunyi tidak pernah dikirim.
    Tanpa class_id: skenario harus ada di katalog umum. Dengan class_id: mahasiswa harus anggota
    kelas itu dan skenario ditetapkan untuk kelasnya.
    """
    if class_id is not None and not await validate_class_access(conn, scenario_id, class_id, user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Anda tidak memiliki izin untuk mengakses skenario pada kelas ini.")
    items = await fetch_public_scenarios(
        conn, user["id"], class_id=class_id, scenario_id=scenario_id, catalog_only=class_id is None
    )
    if not items:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Skenario tidak ditemukan di katalog umum.")
    return items[0]
