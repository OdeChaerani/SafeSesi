from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, TypeVar
from google import genai
from google.genai import errors as genai_errors
from google.genai import types
from pydantic import BaseModel

from core.config import get_settings
from core.errors import LLMServiceError

logger = logging.getLogger("safesesi.llm")

T = TypeVar("T", bound=BaseModel)

ROLE_NAMES = {"A": "Peran A (State Updater)", "B": "Peran B (Client Responder)", "C": "Peran C (Notes Updater)"}


class LLMConfigRejected(LLMServiceError):
    """Gemini menolak kombinasi model/thinking budget dari config (HTTP 400/404). Tidak di-retry."""

    def __init__(self, role: str | None, model: str, thinking_budget: int | None, detail: str) -> None:
        self.role = role
        self.model = model
        self.thinking_budget = thinking_budget
        budget = "tidak dikirim (default model)" if thinking_budget is None else str(thinking_budget)
        super().__init__(
            f"Gemini menolak konfigurasi {ROLE_NAMES.get(role or '', role or 'LLM')}: "
            f"model={model!r}, thinking_budget={budget}. Periksa GEMINI_MODEL_* dan "
            f"GEMINI_THINKING_BUDGET_* untuk peran ini. Detail: {detail}"
        )


class GeminiAsyncClient:
    """Wrapper async untuk Google Gemini SDK (google-genai)."""

    def __init__(self, api_key: str | None = None) -> None:
        settings = get_settings()
        self._api_key = api_key or settings.GEMINI_API_KEY
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if self._client is None:
            if not self._api_key:
                raise LLMServiceError("GEMINI_API_KEY belum dikonfigurasi di environment.")
            self._client = genai.Client(api_key=self._api_key)
        return self._client

    async def _generate(
        self,
        model: str,
        system_instruction: str,
        user_prompt: str,
        temperature: float,
        thinking_budget: int | None,
        extra_config: dict[str, Any],
        role: str | None = None,
    ) -> types.GenerateContentResponse:
        """Satu panggilan generate_content.

        thinking_budget None -> thinking_config tidak dikirim (default model).
        Tidak ada fallback: jika Gemini menolak konfigurasi (HTTP 400/404), dilempar
        LLMConfigRejected yang menyebut peran, model, dan budget, dan giliran gagal.
        """
        client = self._get_client()
        cfg: dict[str, Any] = dict(
            system_instruction=system_instruction,
            temperature=temperature,
            **extra_config,
        )
        if thinking_budget is not None:
            cfg["thinking_config"] = types.ThinkingConfig(thinking_budget=thinking_budget)

        t_start = time.perf_counter()
        try:
            response = await client.aio.models.generate_content(
                model=model, contents=user_prompt, config=types.GenerateContentConfig(**cfg)
            )
        except genai_errors.ClientError as exc:
            if getattr(exc, "code", None) in (400, 404):
                raise LLMConfigRejected(role, model, thinking_budget, str(exc)) from exc
            raise
        elapsed_ms = int((time.perf_counter() - t_start) * 1000)
        usage = response.usage_metadata
        logger.debug(
            "Gemini %s: %d ms | prompt %s tok, cached %s, thoughts %s, output %s",
            model,
            elapsed_ms,
            getattr(usage, "prompt_token_count", None),
            getattr(usage, "cached_content_token_count", None),
            getattr(usage, "thoughts_token_count", None),
            getattr(usage, "candidates_token_count", None),
        )
        return response

    async def generate_json(
        self,
        model: str,
        system_instruction: str,
        user_prompt: str,
        response_schema: type[T],
        temperature: float = 0.2,
        thinking_budget: int | None = 0,
        role: str | None = None,
    ) -> T:
        """Menghasilkan structured output JSON yang tervalidasi dengan skema Pydantic."""
        t_start = time.perf_counter()
        try:
            response = await self._generate(
                model,
                system_instruction,
                user_prompt,
                temperature,
                thinking_budget,
                {"response_mime_type": "application/json", "response_schema": response_schema},
                role=role,
            )
            data = json.loads(response.text or "{}")
            return response_schema.model_validate(data)
        except LLMConfigRejected:
            raise
        except Exception as exc:
            elapsed = time.perf_counter() - t_start
            logger.exception("Gagal menghasilkan JSON terstruktur dari Gemini (%.3fs): %s", elapsed, exc)
            raise LLMServiceError(f"Gagal memproses respons AI terstruktur: {exc}") from exc

    async def generate_text(
        self,
        model: str,
        system_instruction: str,
        user_prompt: str,
        temperature: float = 0.7,
        thinking_budget: int | None = 0,
        role: str | None = None,
    ) -> str:
        """Menghasilkan teks natural dalam Bahasa Indonesia."""
        t_start = time.perf_counter()
        try:
            response = await self._generate(
                model, system_instruction, user_prompt, temperature, thinking_budget, {}, role=role
            )
            return (response.text or "").strip()
        except LLMConfigRejected:
            raise
        except Exception as exc:
            elapsed = time.perf_counter() - t_start
            logger.exception("Gagal menghasilkan teks dari Gemini (%.3fs): %s", elapsed, exc)
            raise LLMServiceError(f"Gagal menghasilkan ucapan klien: {exc}") from exc

    async def probe(self, model: str, thinking_budget: int | None, role: str | None = None) -> None:
        """Panggilan ringan untuk memastikan Gemini menerima kombinasi model + thinking budget."""
        await self._generate(
            model,
            "Jawab dengan satu kata.",
            "ok",
            0.0,
            thinking_budget,
            {"max_output_tokens": 8},
            role=role,
        )


def role_llm_configs(settings: Any) -> dict[str, tuple[str, int | None]]:
    """Model dan thinking budget per peran dari config."""
    return {
        "A": (settings.GEMINI_MODEL_STATE, settings.GEMINI_THINKING_BUDGET_STATE),
        "B": (settings.GEMINI_MODEL_RESPONDER, settings.GEMINI_THINKING_BUDGET_RESPONDER),
        "C": (settings.GEMINI_MODEL_NOTES, settings.GEMINI_THINKING_BUDGET_NOTES),
    }


async def validate_llm_configs(settings: Any, client: "GeminiAsyncClient | None" = None) -> None:
    """Validasi startup: satu panggilan ringan per kombinasi model + budget yang dipakai.

    Melempar LLMConfigRejected jika Gemini menolak salah satunya (startup harus gagal).
    Error lain (jaringan, kuota, 5xx) hanya dicatat sebagai warning agar gangguan
    sementara tidak mencegah aplikasi berjalan.
    """
    llm = client or get_gemini_client()
    # Peran dengan kombinasi sama cukup diuji sekali
    combos: dict[tuple[str, int | None], list[str]] = {}
    for role, combo in role_llm_configs(settings).items():
        combos.setdefault(combo, []).append(role)

    async def check(combo: tuple[str, int | None], roles: list[str]) -> None:
        model, budget = combo
        try:
            await llm.probe(model, budget, role="/".join(roles))
            logger.info("Validasi LLM %s OK: model=%s, thinking_budget=%s", "/".join(roles), model, budget)
        except LLMConfigRejected:
            raise
        except Exception as exc:
            logger.warning(
                "Validasi LLM %s tidak dapat diselesaikan (bukan penolakan config): %s",
                "/".join(roles),
                exc,
            )

    results = await asyncio.gather(
        *(check(combo, roles) for combo, roles in combos.items()), return_exceptions=True
    )
    rejected = [r for r in results if isinstance(r, LLMConfigRejected)]
    if rejected:
        for extra in rejected[1:]:
            logger.error("%s", extra)
        raise rejected[0]
    for r in results:
        if isinstance(r, BaseException):
            raise r


_gemini_client: GeminiAsyncClient | None = None


def get_gemini_client() -> GeminiAsyncClient:
    """Mengembalikan singleton instance GeminiAsyncClient."""
    global _gemini_client
    if _gemini_client is None:
        _gemini_client = GeminiAsyncClient()
    return _gemini_client
