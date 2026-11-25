"""Pemulihan darurat: atur ulang kata sandi sebuah akun, atau buat admin pertama. Dijalankan manual di server.

    python -m scripts.reset_user_password --email admin@kampus.ac.id
    python -m scripts.reset_user_password --email admin@kampus.ac.id --create-admin --name "Nama Admin"

Dijalankan dari folder backend/ dengan DATABASE_URL terisi (backend/.env). Kata sandi diminta lewat
prompt tersembunyi dan tidak pernah dicetak atau dilewatkan lewat argumen baris perintah.
"""
from __future__ import annotations

import argparse
import asyncio
import getpass
import sys
from typing import Any

import asyncpg

from core.config import get_settings
from core.security import hash_password, password_problem
from repositories.auth import revoke_all_refresh_families


class ResetError(Exception):
    """Kesalahan yang pesannya boleh langsung ditampilkan ke operator."""


async def reset_user_password(
    conn: asyncpg.Connection, email: str, password: str, *, create_admin: bool = False, name: str | None = None
) -> dict[str, Any]:
    """Inti skrip (terpisah dari CLI agar bisa dites). Mengembalikan {email, created}."""
    email = email.strip()
    problem = password_problem(password)
    if problem:
        raise ResetError(problem)
    if create_admin and not (name and name.strip()):
        raise ResetError("--create-admin membutuhkan --name.")
    password_hash = hash_password(password)

    async with conn.transaction():
        user = await conn.fetchrow(
            "SELECT id, email FROM users WHERE lower(email) = lower($1) AND deleted_at IS NULL FOR UPDATE", email
        )
        if user is not None:
            if create_admin:
                raise ResetError(f"Akun {user['email']} sudah ada. Jalankan tanpa --create-admin untuk mengatur ulang kata sandinya.")
            # Token aktivasi/reset yang masih menggantung ikut dibatalkan; activated_at diisi bila kosong.
            await conn.execute(
                """
                UPDATE users
                SET password_hash = $2, activated_at = COALESCE(activated_at, now()),
                    activation_token_hash = NULL, activation_token_expires_at = NULL,
                    activation_token_purpose = 'activation'
                WHERE id = $1
                """,
                user["id"],
                password_hash,
            )
            await revoke_all_refresh_families(conn, user["id"])
            return {"email": user["email"], "created": False}

        if await conn.fetchval("SELECT 1 FROM users WHERE lower(email) = lower($1)", email):
            raise ResetError(f"Akun {email} sudah dihapus; skrip ini tidak memulihkan akun yang dihapus.")
        if not create_admin:
            raise ResetError(f"Akun {email} tidak ditemukan. Tambahkan --create-admin --name untuk membuat admin baru.")
        row = await conn.fetchrow(
            """
            INSERT INTO users (name, email, role, password_hash, activated_at)
            VALUES ($1, $2, 'admin'::user_role, $3, now())
            RETURNING email
            """,
            name.strip(),
            email,
            password_hash,
        )
        return {"email": row["email"], "created": True}


async def _run(args: argparse.Namespace, password: str) -> dict[str, Any]:
    conn = await asyncpg.connect(get_settings().DATABASE_URL)
    try:
        return await reset_user_password(conn, args.email, password, create_admin=args.create_admin, name=args.name)
    finally:
        await conn.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Atur ulang kata sandi akun atau buat admin pertama.")
    parser.add_argument("--email", required=True)
    parser.add_argument("--create-admin", action="store_true", help="buat admin baru bila akun belum ada")
    parser.add_argument("--name", help="nama admin baru (wajib bersama --create-admin)")
    args = parser.parse_args(argv)

    password = getpass.getpass("Kata sandi baru: ")
    if password != getpass.getpass("Ulangi kata sandi baru: "):
        print("Kata sandi tidak sama. Tidak ada yang diubah.", file=sys.stderr)
        return 1
    try:
        result = asyncio.run(_run(args, password))
    except ResetError as exc:
        print(f"Gagal: {exc}", file=sys.stderr)
        return 1
    print(f"{'Admin baru dibuat' if result['created'] else 'Kata sandi diubah'}: {result['email']}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
