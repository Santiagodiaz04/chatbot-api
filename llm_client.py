# llm_client.py - Célula inteligente: IA como cerebro principal con datos de la BD
"""
- Respuesta principal generada por Gemini usando contexto real de la BD (propiedades/proyectos).
- Reintentos ante 429 (Too Many Requests) con backoff.
- Si Gemini falla, se usa el borrador del motor de reglas como fallback.
"""

import logging
import time
from typing import Any, Dict, List, Optional

import httpx

from config import GEMINI_API_KEY, LLM_ENABLED

logger = logging.getLogger("chatbot-api")

# Reintentos ante 429 (límite de tasa) con espera en segundos
GEMINI_RETRIES = 3
GEMINI_BACKOFF_SEC = 2.0

# Personalidad por defecto: asesor inmobiliario inteligente (secretaria experta)
# La IA recibe contexto real de la BD: nombre de proyecto, título de propiedad, ubicación, precio, características.
DEFAULT_SYSTEM_PROMPT = (
    "Eres la secretaria experta de CTR Bienes Raíces (inmobiliaria). "
    "Usa SIEMPRE el contexto de la base de datos que te damos: nombre del proyecto, título de la propiedad, "
    "ubicación, precio, características (habitaciones, tipo venta/renta). Responde según lo que el usuario "
    "pregunte (por ubicación, por nombre de proyecto o propiedad, por precio, por características). "
    "NUNCA inventes datos; usa SOLO la información que te pasamos. "
    "NUNCA digas 'no hay' sin ofrecer una alternativa o invitar a agendar. "
    "Siempre orienta hacia ver la propiedad o agendar una visita. "
    "Comportamiento: amable, cercana, profesional. Responde en el mismo idioma que el usuario. "
    "Tono conversacional; emojis moderados (🙂🏡📅). "
    "Si el borrador ya ofrece alternativas, refuerza el valor y la invitación a agendar."
)

GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent"
MAX_TOKENS = 500
TIMEOUT = 22.0


def build_data_context(cards: Optional[List[Dict[str, Any]]]) -> str:
    """
    Construye un resumen de los datos (propiedades/proyectos) para que la IA
    tenga contexto real de la BD: nombre de proyecto, título de propiedad,
    ubicación, precio, características. Así la IA responde bien por ubicación,
    nombre, precio o características.
    """
    if not cards or not isinstance(cards, list):
        return "Sin resultados en base de datos para esta búsqueda."

    lines: List[str] = []
    for c in cards[:6]:
        card_type = (c.get("type") or "propiedad").lower()
        titulo = (c.get("titulo") or "").strip() or "Sin título"
        ubicacion = (c.get("ubicacion") or "").strip()
        desc = (c.get("descripcion") or "").strip()[:80]
        if card_type == "proyecto":
            precio = c.get("precio_desde") or ""
            line = f"- Proyecto: {titulo}"
            if ubicacion:
                line += f", ubicación: {ubicacion}"
            if precio:
                line += f", desde {precio}"
            if desc:
                line += f". {desc}"
            lines.append(line)
        else:
            precio = c.get("precio") or ""
            hab = c.get("habitaciones")
            banos = c.get("banos")
            tipo = c.get("tipo") or "venta"
            line = f"- Propiedad: {titulo}, {tipo}"
            if ubicacion:
                line += f", ubicación: {ubicacion}"
            if precio:
                line += f", precio: {precio}"
            if hab is not None:
                line += f", {hab} hab"
            if banos is not None:
                line += f", {banos} baños"
            if desc:
                line += f". {desc}"
            lines.append(line)

    if not lines:
        return "Sin resultados en base de datos para esta búsqueda."
    return "Contexto de la base de datos (usa esto para responder por nombre, ubicación, precio o características):\n" + "\n".join(lines)


def _call_gemini(prompt: str) -> Optional[str]:
    """Llama a Gemini con reintentos ante 429. Devuelve el texto generado o None."""
    if not (GEMINI_API_KEY or "").strip():
        return None
    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.5,
            "maxOutputTokens": MAX_TOKENS,
            "topP": 0.9,
        },
    }
    last_error = None
    for attempt in range(GEMINI_RETRIES):
        try:
            r = httpx.post(
                f"{GEMINI_URL}?key={GEMINI_API_KEY.strip()}",
                json=payload,
                timeout=TIMEOUT,
            )
            if r.status_code == 429:
                last_error = "429 Too Many Requests"
                if attempt < GEMINI_RETRIES - 1:
                    wait = GEMINI_BACKOFF_SEC * (2 ** attempt)
                    logger.warning("Gemini 429, reintento en %.1fs (intento %d/%d)", wait, attempt + 1, GEMINI_RETRIES)
                    time.sleep(w)
                continue
            r.raise_for_status()
            data = r.json()
            candidates = data.get("candidates") or []
            if not candidates:
                return None
            parts = candidates[0].get("content", {}).get("parts") or []
            if not parts:
                return None
            text = (parts[0].get("text") or "").strip()
            if not text or len(text) > 2800:
                return None
            return text
        except httpx.HTTPStatusError as e:
            last_error = str(e)
            if e.response.status_code == 429 and attempt < GEMINI_RETRIES - 1:
                wait = GEMINI_BACKOFF_SEC * (2 ** attempt)
                logger.warning("Gemini 429, reintento en %.1fs", wait)
                time.sleep(wait)
            else:
                break
        except Exception as e:
            last_error = str(e)
            break
    logger.warning("Célula inteligente (Gemini) falló tras reintentos: %s", last_error)
    return None


def generate_full_reply(
    user_message: str,
    data_context: str,
    last_user_message: Optional[str] = None,
    last_bot_message: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Célula como cerebro: Gemini genera la respuesta completa solo con datos de la BD.
    No usa borrador nativo; todo el texto sale de la IA según el contexto de datos.
    """
    if not LLM_ENABLED or not (data_context or "").strip():
        return None

    base = (system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT
    conv = ""
    if last_user_message and last_bot_message:
        conv = f"Intercambio anterior:\nUsuario: {last_user_message[:300]}\nAsistente: {last_bot_message[:400]}\n\n"
    elif last_user_message:
        conv = f"Contexto: {last_user_message[:300]}\n\n"

    prompt = (
        f"{base}\n\n"
        f"{conv}"
        f"Datos actuales de la base de datos (usa SOLO esto para responder):\n{data_context.strip()}\n\n"
        f"Mensaje del usuario: {user_message[:600]}\n\n"
        "Responde al usuario en una sola respuesta breve y natural, usando únicamente los datos anteriores. "
        "No inventes. Si hay proyectos o propiedades listadas, menciónalos. Invita a agendar visita si aplica. "
        "Escribe solo la respuesta al usuario, sin explicaciones ni comillas."
    )
    return _call_gemini(prompt)


def process_response(
    user_message: str,
    draft_reply: str,
    intent: Optional[str] = None,
    data_context: Optional[str] = None,
    last_user_message: Optional[str] = None,
    last_bot_message: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Humaniza el borrador con Gemini, o genera respuesta completa si hay contexto de BD.
    Con reintentos ante 429.
    """
    if not LLM_ENABLED or not (GEMINI_API_KEY or "").strip():
        return None

    # Si hay datos de BD, la célula genera la respuesta completa desde esos datos (nada nativo)
    if data_context and data_context.strip():
        full = generate_full_reply(
            user_message,
            data_context,
            last_user_message=last_user_message,
            last_bot_message=last_bot_message,
            system_prompt=system_prompt,
        )
        if full:
            return full

    # Fallback: humanizar el borrador con Gemini
    conversation_block = ""
    if last_user_message and last_bot_message:
        conversation_block = (
            f"Intercambio anterior:\nUsuario: {last_user_message[:300]}\nAsistente: {last_bot_message[:400]}\n\n"
        )
    elif last_user_message:
        conversation_block = f"Último mensaje del usuario (contexto): {last_user_message[:300]}\n\n"

    data_block = (data_context or "").strip()
    if data_block:
        data_block = f"{data_block}\n\n"

    base_instructions = (system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT
    prompt = (
        f"{base_instructions}\n\n"
        f"{conversation_block}"
        f"Mensaje actual del usuario: {user_message[:600]}\n\n"
        f"{data_block}"
        f"Borrador de respuesta (usa esta información, escribe de forma conversacional):\n{draft_reply[:1800]}\n\n"
        "Escribe únicamente la respuesta final al usuario, sin explicaciones ni comillas."
    )
    return _call_gemini(prompt)


def generate_reply(
    user_message: str,
    draft_reply: str,
    intent: Optional[str] = None,
    data_context: Optional[str] = None,
    last_user_message: Optional[str] = None,
    last_bot_message: Optional[str] = None,
    system_prompt: Optional[str] = None,
) -> Optional[str]:
    """
    Punto de entrada: humaniza/processa la respuesta con la célula inteligente.
    system_prompt: instrucciones desde Admin (chatbot_config: prompt_sistema o instrucciones_ia).
    """
    return process_response(
        user_message=user_message,
        draft_reply=draft_reply,
        intent=intent,
        data_context=data_context,
        last_user_message=last_user_message,
        last_bot_message=last_bot_message,
        system_prompt=system_prompt,
    )
