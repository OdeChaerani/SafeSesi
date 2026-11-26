"""Kelas yang terhubung dengan akun mahasiswa dan skenario yang ditetapkan untuk kelas itu."""
from __future__ import annotations

from typing import Any

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, status

from api.deps import get_db, require_role
from repositories.classes import get_class, is_class_member, list_user_classes
from repositories.scenarios import fetch_public_scenarios
from schemas.student import ClassScenariosResponse, ClassSummary

router = APIRouter(prefix="/classes", tags=["classes"])


@router.get("", response_model=list[ClassSummary])
async def list_my_classes(
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Kelas aktif tempat mahasiswa menjadi anggota: nama, tahun akademik, dan nama dosen."""
    return await list_user_classes(conn, user["id"])


@router.get("/{class_id}/scenarios", response_model=ClassScenariosResponse)
async def list_class_scenarios(
    class_id: int,
    user: dict[str, Any] = Depends(require_role("student")),
    conn: asyncpg.Connection = Depends(get_db),
) -> Any:
    """Skenario yang ditetapkan untuk kelas, hanya untuk anggota kelas itu (ringkasan publik saja)."""
    class_info = await get_class(conn, class_id)
    if not class_info:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=f"Kelas dengan ID {class_id} tidak ditemukan.")
    if not await is_class_member(conn, class_id, user["id"]):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Anda bukan anggota kelas ini.")
    items = await fetch_public_scenarios(conn, user["id"], class_id=class_id)
    return {"class_info": {**class_info, "scenario_count": len(items)}, "items": items}
