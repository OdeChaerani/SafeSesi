from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import AsyncGenerator
import asyncpg
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from api import api_router
from core.config import get_settings
from core.errors import SafeSesiError
from services.llm.gemini_client import validate_llm_configs
from services.simulation.turn_lock import configure_turn_lock, drain_background_tasks

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%H:%M:%S",
)
logger = logging.getLogger("safesesi")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Lifespan context manager untuk mengelola asyncpg connection pool."""
    settings = get_settings()
    pool: asyncpg.Pool | None = None

    # Validasi model + thinking budget per peran sebelum resource lain dibuat.
    # LLMConfigRejected dibiarkan lolos: startup gagal dengan pesan peran/model/budget.
    if settings.GEMINI_VALIDATE_ON_STARTUP and settings.GEMINI_API_KEY:
        await validate_llm_configs(settings)
    elif settings.GEMINI_VALIDATE_ON_STARTUP:
        logger.warning("GEMINI_API_KEY kosong; validasi konfigurasi LLM dilewati.")

    if settings.DATABASE_URL:
        try:
            logger.info("Menginisialisasi connection pool asyncpg...")
            # statement_cache_size=0 diatur untuk kompatibilitas penuh dengan Supabase Transaction Pooler
            pool = await asyncio.wait_for(
                asyncpg.create_pool(
                    dsn=settings.DATABASE_URL,
                    statement_cache_size=0,
                    min_size=1,
                    max_size=10,
                ),
                timeout=3.0,
            )
            app.state.db_pool = pool
            logger.info("Connection pool asyncpg berhasil diinisialisasi.")
        except Exception as exc:
            logger.warning("Gagal menginisialisasi connection pool asyncpg: %s", exc)
            app.state.db_pool = None
    else:
        logger.info("DATABASE_URL kosong. db_pool disetel ke None.")
        app.state.db_pool = None

    configure_turn_lock(app.state.db_pool, timeout_s=settings.TURN_LOCK_TIMEOUT_S)

    yield

    # Tunggu Peran C background agar catatan topik akhir tidak hilang saat shutdown
    await drain_background_tasks(timeout_s=settings.NOTES_TIMEOUT_S + 5)
    configure_turn_lock(None)

    if pool is not None:
        logger.info("Menutup connection pool asyncpg...")
        await pool.close()
        logger.info("Connection pool asyncpg telah ditutup.")


settings = get_settings()

app = FastAPI(
    title="SafeSesi Backend API",
    description="Backend simulasi klien virtual konseling Motivational Interviewing (MI) SafeSesi.",
    version="1.0.0",
    lifespan=lifespan,
)

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(SafeSesiError)
async def safesesi_error_handler(request: Request, exc: SafeSesiError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"detail": exc.message},
    )


# Registrasi router sistem dan API
app.include_router(api_router, prefix="")
app.include_router(api_router, prefix="/api/v1")
