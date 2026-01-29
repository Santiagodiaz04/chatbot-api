# llm_client.py - IA generativa (gratis) para humanizar respuestas
"""Usa Google Gemini (free tier). Solo reescribe el texto; cards, citas y BD siguen igual."""

import logging
from typing import Optional

import httpx

from config import GEMINI_API_KEY, LLM_ENABLED

logger = logging.getLogger("chatbot-api")

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MAX_TOKENS = 256
TIMEOUT = 15.0


def generate_reply(
    user_message: str,
    draft_reply: str,
    intent: Optional[str] = None,
) -> Optional[str]:
    """
    Reescribe el borrador de respuesta en un tono más natural.
    Si no hay API key o falla, devuelve None (se usa el draft).
    """
    if not LLM_ENABLED or not (GEMINI_API_KEY or "").strip():
        return None

    prompt = (
        "Eres el asistente de una inmobiliaria (CTR Bienes Raíces). "
        "Reescribe la siguiente respuesta del bot de forma natural y conversacional, "
        "en el mismo idioma que el usuario. Mantén toda la información (precios, cantidades, fechas). "
        "Responde SOLO con el texto reescrito, sin explicaciones ni comillas.\n\n"
        f"Usuario dijo: {user_message[:500]}\n\n"
        f"Respuesta actual del bot: {draft_reply[:1500]}"
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.6,
            "maxOutputTokens": MAX_TOKENS,
            "topP": 0.9,
        },
    }

    try:
        r = httpx.post(
            f"{GEMINI_URL}?key={GEMINI_API_KEY.strip()}",
            json=payload,
            timeout=TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        candidates = data.get("candidates") or []
        if not candidates:
            return None
        parts = candidates[0].get("content", {}).get("parts") or []
        if not parts:
            return None
        text = (parts[0].get("text") or "").strip()
        if not text or len(text) > 2000:
            return None
        return text
    except Exception as e:
        logger.warning("LLM humanize failed: %s", e)
        return None
