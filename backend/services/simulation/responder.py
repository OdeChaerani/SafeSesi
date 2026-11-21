from __future__ import annotations

import json
import logging
import re
from typing import Any
from core.config import get_settings
from prompts.prompt_b_responder import PROMPT_B_VERSION, SYSTEM_INSTRUCTION_B
from schemas.client_state import ClientState
from services.llm.gemini_client import LLMConfigRejected, get_gemini_client
from services.simulation.disclosure import filter_hidden_facts

MAX_REPLY_WORDS = 40
MAX_REPLY_SENTENCES = 3
# Batas kalimat: tanda akhir lalu spasi lalu huruf besar/kutip. "saya... ya" (lanjut huruf kecil) bukan batas.
_SENTENCE_END = re.compile(r"(?<=[.!?])\s+(?=[A-Z\"“'(])")


def limit_reply(text: str, max_words: int = MAX_REPLY_WORDS, max_sentences: int = MAX_REPLY_SENTENCES) -> str:
    """Penjamin panjang ucapan klien bila Peran B melewati batas di prompt: potong di akhir kalimat.

    Kalimat pertama yang sendirian sudah lebih dari batas dipotong per kata dan diakhiri "…".
    """
    text = text.strip()
    kept: list[str] = []
    words = 0
    for sentence in _SENTENCE_END.split(text):
        n = len(sentence.split())
        if len(kept) == max_sentences or (kept and words + n > max_words):
            break
        if not kept and n > max_words:
            return " ".join(sentence.split()[:max_words]).rstrip(",;:") + "…"
        kept.append(sentence)
        words += n
    return " ".join(kept)

logger = logging.getLogger("safesesi.simulation.responder")


async def generate_client_response_llm(
    persona: dict[str, Any],
    case_data: dict[str, Any],
    new_state: ClientState | dict[str, Any],
    topic_notes: list[dict[str, Any]],
    transcript_history: list[dict[str, Any]],
    counselor_utterance: str,
    hidden_facts: list[dict[str, Any]],
    decision_only: bool = False,
) -> str:
    """Peran B: Client Responder (menghasilkan ucapan respon klien virtual).

    decision_only=True (mode split): new_state berasal dari State Decision Agent; emosi ditulis
    tanpa emotion_cause (penyebabnya belum diperbarui pada giliran ini).

    PEMBATASAN DI LEVEL KODE (lihat services/simulation/disclosure.py):
    Fakta masuk prompt hanya jika Disclosure saat ini >= tingkat minimal fakta,
    dan saat Discord tampak hanya fakta yang sudah terungkap.
    Dilengkapi mekanisme retry 1x.
    """
    settings = get_settings()
    llm = get_gemini_client()

    state_dict = (
        new_state.model_dump() if isinstance(new_state, ClientState) else new_state
    )

    allowed_facts = filter_hidden_facts(
        hidden_facts,
        disclosure_level=state_dict.get("disclosure_level"),
        discord_present=bool(state_dict.get("discord_present")),
        topic_notes=topic_notes,
    )
    filtered_hidden_facts = [
        {k: v for k, v in fact.items() if k not in ("min_disclosure_level", "sort_order")}
        for fact in allowed_facts
    ]

    try:
        client_age = int(persona.get("age", 30))
    except (ValueError, TypeError):
        client_age = 30

    if client_age < 25:
        addressing_guide = (
            "Karena Anda masih muda, Anda boleh memanggil konselor 'Kak' (misal: 'Halo Kak', 'Kabar baik Kak')."
        )
    else:
        addressing_guide = (
            "Karena Anda sudah dewasa/lebih berumur, bicaralah secara langsung dan sopan TANPA embel-embel panggilan (JANGAN memanggil 'Kak', dan JANGAN menebak 'Mas/Mbak/Pak/Bu'). Cukup jawab langsung seperti: 'Halo, selamat pagi', 'Kabar baik, terima kasih'."
        )

    emotion_line = (
        f"- Emosi: {state_dict.get('emotion_type')}"
        if decision_only
        else f"- Emosi: {state_dict.get('emotion_type')} ({state_dict.get('emotion_cause')})"
    )

    # Urutan: bagian statis per sesi dulu (konteks, persona, kasus, petunjuk), lalu bagian
    # yang berubah tiap giliran, riwayat & ucapan terkini di akhir (prefix stabil untuk caching).
    user_prompt = f"""
### Konteks Situasi:
Anda sedang berada dalam sesi konseling tatap maya (online video call) resmi yang sudah dijadwalkan bersama konselor Anda (pengguna adalah konselor).

### Profil Persona Anda:
- Nama: {persona.get('name')}
- Usia / Gender: {persona.get('age')} tahun, {persona.get('gender')}
- Pekerjaan: {persona.get('occupation')}
- Latar Belakang: {persona.get('family_background')}
- Kepribadian Konkret: {persona.get('personality')}
- Gaya Komunikasi: {persona.get('communication_style')}

### Kasus & Masalah Anda:
- Permasalahan Utama: {case_data.get('main_problem')}
- Riwayat & Dampak: {case_data.get('history_impact')}
- Harapan & Konteks Perubahan: {case_data.get('expectation_change_context')}

### Petunjuk Menanggapi:
1. Panggilan ke Konselor (Usia Anda: {client_age} tahun):
   - {addressing_guide}
   - DILARANG menebak konselor adalah pria ('Mas'/'Pak') secara sepihak.
2. Jika konselor hanya menyapa ('Halo', 'Hai', 'Selamat pagi', dll.), balaslah sapaan tersebut secara proporsional dan santun. JANGAN bertanya curiga seperti 'Ada apa ya?' karena Anda tahu ini adalah sesi konseling Anda.
3. Jika konselor bertanya kabar ('Gimana kabarnya?'), jawab kondisi kabar Anda secara ringkas dan wajar. JANGAN melompat langsung membahas topik masalah (seperti rokok atau masalah pribadi) sebelum konselor mulai mengeksplorasinya.
4. Bicaralah wajar dan ringkas (maksimal 2–3 kalimat, tidak lebih dari 40 kata) dengan gaya lisan santai sesuai karakter persona Anda.

### Informasi Tersembunyi (Boleh Diungkap Bertahap HANYA JIKA Konteks Sangat Mendukung):
{json.dumps(filtered_hidden_facts, indent=2, ensure_ascii=False, default=str) if filtered_hidden_facts else "[] (Belum ada informasi tersembunyi yang boleh Anda ungkapkan saat ini)"}

### Kondisi Emosi & Keterbukaan Anda Saat Ini:
{emotion_line}
- Tingkat Keterbukaan: {state_dict.get('disclosure_level')}
- Ambivalensi: {state_dict.get('ambivalence_lean')} (Ingin Berubah: {state_dict.get('reasons_to_change')} | Bertahan: {state_dict.get('reasons_to_maintain')})
- Ketegangan Hubungan (Discord): {'ADA' if state_dict.get('discord_present') else 'Tidak Tampak'} {f"- Catatan: {state_dict.get('discord_context')}" if state_dict.get('discord_present') else ''}

### Catatan Pembahasan Topik Sejauh Ini:
{json.dumps([{"topik": t.get("topic_name"), "catatan": t.get("description")} for t in topic_notes], indent=2, ensure_ascii=False, default=str)}

### Riwayat Percakapan Sebelumnya:
{json.dumps([{"speaker": t.get("speaker"), "content": t.get("content")} for t in transcript_history[-8:]], indent=2, ensure_ascii=False, default=str) if transcript_history else "[] (Belum ada percakapan sebelumnya, sesi baru dimulai)"}

### Ucapan Konselor Terkini:
"{counselor_utterance}"

Tanggapi ucapan konselor terkini sesuai Petunjuk Menanggapi di atas.
""".strip()

    last_exc: Exception | None = None
    for attempt in range(2):
        try:
            reply = await llm.generate_text(
                model=settings.GEMINI_MODEL_RESPONDER,
                system_instruction=SYSTEM_INSTRUCTION_B,
                user_prompt=user_prompt,
                temperature=0.7,
                thinking_budget=settings.GEMINI_THINKING_BUDGET_RESPONDER,
                role="B",
            )
            return limit_reply(reply)
        except LLMConfigRejected:
            raise  # salah konfigurasi: retry tidak menolong
        except Exception as exc:
            last_exc = exc
            logger.warning(
                "Percobaan %d pembuatan Client Responder gagal: %s", attempt + 1, exc
            )

    raise last_exc or RuntimeError("Gagal menghasilkan respons klien setelah 2 percobaan.")
