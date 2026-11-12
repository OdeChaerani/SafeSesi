from __future__ import annotations

import json
import logging
from typing import Any
from core.config import get_settings
from prompts.prompt_a_state import PROMPT_A_VERSION, SYSTEM_INSTRUCTION_A
from schemas.client_state import ClientState
from services.llm.gemini_client import get_gemini_client
from services.simulation.disclosure import enforce_disclosure_floor

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
    llm = get_gemini_client()

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

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            new_state = await llm.generate_json(
                model=settings.GEMINI_MODEL_STATE,
                system_instruction=SYSTEM_INSTRUCTION_A,
                user_prompt=user_prompt,
                response_schema=ClientState,
                temperature=0.2,
            )
            break
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Percobaan %d pembaruan State Updater gagal: %s", attempt + 1, exc
            )
    else:
        raise last_exc or RuntimeError("Gagal memperbarui status klien setelah 2 percobaan.")

    return _apply_disclosure_floor(current_state.get("disclosure_level"), new_state)


def _apply_disclosure_floor(previous_level: Any, new_state: ClientState) -> ClientState:
    """Disclosure tidak pernah turun (BRD Lampiran 2), ditegakkan di kode, bukan oleh LLM."""
    floored = enforce_disclosure_floor(previous_level, new_state.disclosure_level)
    if floored == new_state.disclosure_level:
        return new_state
    logger.warning(
        "State Updater mengembalikan disclosure_level %r di bawah tingkat sebelumnya %r; "
        "dipertahankan %r.",
        new_state.disclosure_level,
        previous_level,
        floored,
    )
    return new_state.model_copy(update={"disclosure_level": floored})
