from __future__ import annotations

from typing import Any, Literal
import asyncpg
from fastapi import APIRouter, Depends, Query

from api.deps import get_current_user, get_db
from repositories.scenarios import get_catalog_scenarios
from schemas.scenario import CatalogScenarioResponse

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
    user: dict[str, Any] = Depends(get_current_user),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Mengambil daftar skenario latihan mandiri (katalog umum) beserta status pengerjaan mahasiswa."""
    return await get_catalog_scenarios(
        conn=conn,
        student_id=user["id"],
        search=search,
        status_filter=status,
    )
