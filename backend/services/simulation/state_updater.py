from __future__ import annotations

import json
import logging
from typing import Any
from core.config import get_settings
from prompts.prompt_a_state import PROMPT_A_VERSION, SYSTEM_INSTRUCTION_A
from prompts.prompt_state_decision import (
    SYSTEM_INSTRUCTION_STATE_DECISION,
    SYSTEM_INSTRUCTION_STATE_DECISION_NO_REASON,
)
from prompts.prompt_state_detail import SYSTEM_INSTRUCTION_STATE_DETAIL
from schemas.client_state import (
    DETAIL_FIELDS,
    ClientState,
    StateDecision,
    StateDecisionNoReason,
    StateDetail,
)
from services.llm.gemini_client import LLMConfigRejected, get_gemini_client
from services.simulation.disclosure import resolve_disclosure

logger = logging.getLogger("safesesi.simulation.state")


async def update_client_state_llm(
    counselor_utterance: str,
    current_state: dict[str, Any],
    persona: dict[str, Any],
    case_data: dict[str, Any],
    transcript_history: list[dict[str, Any]],
    topic_notes: list[dict[str, Any]] | None = None,
) -> ClientState:
    """Peran A: State Updater (menghasilkan pembaruan ClientState menggunakan LLM).

    Dilengkapi mekanisme retry 1x jika pemanggilan model atau parsing gagal.
    """
    settings = get_settings()

    notes_section = ""
    if topic_notes:
        notes_section = f"""
### Catatan Perkembangan Topik:
{json.dumps([{"topik": t.get("topic_name"), "catatan": t.get("description")} for t in topic_notes], indent=2, ensure_ascii=False, default=str)}
"""

    clean_state = {
        "emotion_type": current_state.get("emotion_type"),
        "emotion_cause": current_state.get("emotion_cause"),
        "disclosure_level": current_state.get("disclosure_level"),
        "disclosure_trigger": current_state.get("disclosure_trigger"),
        "reasons_to_change": current_state.get("reasons_to_change"),
        "reasons_to_maintain": current_state.get("reasons_to_maintain"),
        "ambivalence_lean": current_state.get("ambivalence_lean"),
        "discord_present": current_state.get("discord_present", False),
        "discord_context": current_state.get("discord_context"),
        "discord_response": current_state.get("discord_response"),
    }

    # Urutan: konteks skenario statis dulu, lalu bagian dinamis; riwayat & ucapan di akhir.
    user_prompt = f"""
### Konteks Skenario:
- Nama Klien: {persona.get('name')}
- Usia / Gender: {persona.get('age')} tahun, {persona.get('gender')}
- Kepribadian: {persona.get('personality')}
- Gaya Komunikasi: {persona.get('communication_style')}
- Permasalahan Kasus: {case_data.get('main_problem')}
- Riwayat & Dampak: {case_data.get('history_impact')}
- Konteks Perubahan: {case_data.get('expectation_change_context')}
{notes_section}
### Kondisi Klien Saat Ini (Sebelum Giliran Konselor Terkini):
{json.dumps(clean_state, indent=2, ensure_ascii=False, default=str)}

### Riwayat Percakapan Terakhir:
{json.dumps([{"speaker": t.get("speaker"), "content": t.get("content")} for t in transcript_history[-8:]], indent=2, ensure_ascii=False, default=str)}

### Ucapan Konselor Terkini:
"{counselor_utterance}"

Analisis ucapan konselor terkini di atas dan tentukan pembaruan kondisi klien (Client State).
Keluarkan JSON yang mematuhi skema ClientState.
""".strip()

    new_state = await _generate_json_with_retry(
        "State Updater",
        model=settings.GEMINI_MODEL_STATE,
        system_instruction=SYSTEM_INSTRUCTION_A,
        user_prompt=user_prompt,
        response_schema=ClientState,
        temperature=0.2,
        thinking_budget=settings.GEMINI_THINKING_BUDGET_STATE,
        role="A",
    )
    return _apply_disclosure_floor(current_state.get("disclosure_level"), new_state)


async def _generate_json_with_retry(label: str, **kwargs: Any) -> Any:
    """generate_json dengan retry 1x; penolakan konfigurasi tidak di-retry."""
    llm = get_gemini_client()
    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            return await llm.generate_json(**kwargs)
        except LLMConfigRejected:
            raise  # salah konfigurasi: retry tidak menolong
        except Exception as exc:
            last_exc = exc
            logger.warning("Percobaan %d pembaruan %s gagal: %s", attempt + 1, label, exc)
    raise last_exc or RuntimeError(f"Gagal menjalankan {label} setelah 2 percobaan.")


# ---------------------------------------------------------------------------
# Mode split: State Decision Agent + State Detail Agent
# ---------------------------------------------------------------------------

DECISION_STATE_KEYS = ("emotion_type", "disclosure_level", "discord_present", "ambivalence_lean")


def _brief_context(
    persona: dict[str, Any],
    case_data: dict[str, Any],
    transcript_history: list[dict[str, Any]],
    history_turns: int,
) -> tuple[str, str]:
    """Ringkasan persona/kasus dan riwayat terakhir (input yang dipangkas untuk mode split)."""
    context = f"""### Konteks Klien:
- Nama: {persona.get('name')} ({persona.get('age')} tahun, {persona.get('gender')})
- Kepribadian: {persona.get('personality')}
- Gaya Komunikasi: {persona.get('communication_style')}
- Permasalahan Utama: {case_data.get('main_problem')}"""
    recent = [{"speaker": t.get("speaker"), "content": t.get("content")} for t in transcript_history[-history_turns:]]
    history = json.dumps(recent, indent=2, ensure_ascii=False, default=str) if recent else "[] (sesi baru dimulai)"
    return context, history


async def update_client_state_decision(
    counselor_utterance: str,
    current_state: dict[str, Any],
    persona: dict[str, Any],
    case_data: dict[str, Any],
    transcript_history: list[dict[str, Any]],
    *,
    with_reasons: bool = True,
    history_turns: int = 4,
) -> StateDecision | StateDecisionNoReason:
    """State Decision Agent (Peran A, mode split): memutuskan disclosure_level, discord_present,
    ambivalence_lean, dan emosi singkat yang dibutuhkan Peran B pada giliran ini.

    Penamaan mengikuti pola agen berbasis fungsi pada Steenstra dkk. (2025). Aturan Disclosure
    di kode tetap berlaku pada keluarannya. with_reasons=False dan history_turns hanya diubah
    oleh skrip replay untuk pembanding.
    """
    settings = get_settings()
    context, history = _brief_context(persona, case_data, transcript_history, history_turns)
    previous = {k: current_state.get(k) for k in DECISION_STATE_KEYS}
    user_prompt = f"""
{context}

### Kondisi Klien Sebelum Giliran Ini:
{json.dumps(previous, indent=2, ensure_ascii=False, default=str)}

### Riwayat Percakapan Terakhir:
{history}

### Ucapan Konselor Terkini:
"{counselor_utterance}"

Putuskan kondisi klien untuk menjawab ucapan konselor terkini.
""".strip()

    decision = await _generate_json_with_retry(
        "State Decision Agent",
        model=settings.GEMINI_MODEL_STATE_DECISION,
        system_instruction=SYSTEM_INSTRUCTION_STATE_DECISION if with_reasons else SYSTEM_INSTRUCTION_STATE_DECISION_NO_REASON,
        user_prompt=user_prompt,
        response_schema=StateDecision if with_reasons else StateDecisionNoReason,
        temperature=0.2,
        thinking_budget=settings.GEMINI_THINKING_BUDGET_STATE_DECISION,
        role="state_decision",
    )
    return _apply_disclosure_floor(current_state.get("disclosure_level"), decision)


def provisional_state(previous_state: dict[str, Any], decision: StateDecision) -> ClientState:
    """Client State giliran ini sebelum State Detail Agent selesai: keputusan State Decision Agent,
    alasan singkatnya di kolom deskriptif yang sepadan, sisanya salinan state sebelumnya."""
    discord = decision.discord_present
    return ClientState(
        emotion_type=decision.emotion_short,
        emotion_cause=previous_state.get("emotion_cause"),
        disclosure_level=decision.disclosure_level,
        disclosure_trigger=decision.disclosure_reason,
        reasons_to_change=previous_state.get("reasons_to_change"),
        reasons_to_maintain=previous_state.get("reasons_to_maintain"),
        ambivalence_lean=decision.ambivalence_lean,
        discord_present=discord,
        # Kolom Discord hanya berisi saat Discord tampak (sama dengan aturan prompt Peran A).
        discord_context=decision.discord_reason if discord else None,
        discord_response=previous_state.get("discord_response") if discord else None,
    )


async def update_client_state_detail(
    counselor_utterance: str,
    client_reply: str,
    previous_state: dict[str, Any],
    decided_state: ClientState,
    persona: dict[str, Any],
    case_data: dict[str, Any],
    transcript_history: list[dict[str, Any]],
    *,
    history_turns: int = 4,
) -> StateDetail:
    """State Detail Agent (Peran A, mode split): mengisi field deskriptif Client State setelah
    respons klien terkirim, dengan membaca ucapan konselor dan jawaban klien dari Peran B.

    Penamaan mengikuti pola agen berbasis fungsi pada Steenstra dkk. (2025). Skema StateDetail
    tidak memuat disclosure_level/discord_present/ambivalence_lean, jadi keputusan State
    Decision Agent tidak bisa diubah di sini.
    """
    settings = get_settings()
    context, history = _brief_context(persona, case_data, transcript_history, history_turns)
    previous = {k: previous_state.get(k) for k in (*DETAIL_FIELDS, "disclosure_level", "discord_present", "ambivalence_lean")}
    decided = {
        "disclosure_level": decided_state.disclosure_level,
        "discord_present": decided_state.discord_present,
        "ambivalence_lean": decided_state.ambivalence_lean,
        "emosi_singkat": decided_state.emotion_type,
    }
    user_prompt = f"""
{context}

### Kondisi Klien Sebelum Giliran Ini:
{json.dumps(previous, indent=2, ensure_ascii=False, default=str)}

### Keputusan Giliran Ini (tetap, jangan diubah):
{json.dumps(decided, indent=2, ensure_ascii=False, default=str)}

### Riwayat Percakapan Terakhir:
{history}

### Giliran Ini:
- Konselor: "{counselor_utterance}"
- Klien: "{client_reply}"

Lengkapi catatan deskriptif Client State untuk giliran ini.
""".strip()

    detail = await _generate_json_with_retry(
        "State Detail Agent",
        model=settings.GEMINI_MODEL_STATE_DETAIL,
        system_instruction=SYSTEM_INSTRUCTION_STATE_DETAIL,
        user_prompt=user_prompt,
        response_schema=StateDetail,
        temperature=0.2,
        thinking_budget=settings.GEMINI_THINKING_BUDGET_STATE_DETAIL,
        role="state_detail",
    )
    if not decided_state.discord_present:
        detail = detail.model_copy(update={"discord_context": None, "discord_response": None})
    return detail


def _apply_disclosure_floor(previous_level: Any, new_state: Any) -> Any:
    """Aturan Disclosure BRD Lampiran 2, ditegakkan di kode, bukan oleh LLM.

    Disclosure tidak pernah turun; saat Discord tampak, Disclosure tetap pada tingkat sebelumnya.
    """
    resolved = resolve_disclosure(
        previous_level, new_state.disclosure_level, new_state.discord_present
    )
    if resolved == new_state.disclosure_level:
        return new_state
    reason = (
        "Discord tampak, tingkat dikunci"
        if new_state.discord_present
        else "di bawah tingkat sebelumnya"
    )
    logger.warning(
        "State Updater mengembalikan disclosure_level %r (%s; sebelumnya %r); dipakai %r.",
        new_state.disclosure_level,
        reason,
        previous_level,
        resolved,
    )
    return new_state.model_copy(update={"disclosure_level": resolved})
