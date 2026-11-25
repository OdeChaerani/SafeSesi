from __future__ import annotations

from fastapi import APIRouter
from api.admin import router as admin_router
from api.auth import router as auth_router
from api.classes import router as classes_router
from api.evaluations import router as evaluations_router
from api.scenarios import router as scenarios_router
from api.sessions import router as sessions_router
from api.speech import router as speech_router
from api.system import router as system_router

api_router = APIRouter()
api_router.include_router(system_router)
api_router.include_router(scenarios_router)
api_router.include_router(sessions_router)
api_router.include_router(classes_router)
api_router.include_router(auth_router)
api_router.include_router(admin_router)
api_router.include_router(evaluations_router)
api_router.include_router(speech_router)

__all__ = ["api_router"]
