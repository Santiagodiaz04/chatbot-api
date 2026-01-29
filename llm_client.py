# llm_client.py - Célula inteligente: IA para análisis, contexto de datos y conversación fluida
"""
Procesa respuestas con Gemini: contexto de BD (propiedades/proyectos), historial reciente
y borrador del bot. Personalidad: secretaria experta inmobiliaria; nunca "no hay" sin alternativa.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from config import GEMINI_API_KEY, LLM_ENABLED

logger = logging.getLogger("chatbot-api")

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
MAX_TOKENS = 400
TIMEOUT = 18.0


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
    Célula inteligente: procesa el mensaje del usuario, el borrador del bot y el contexto
    (datos de BD, último intercambio). system_prompt: instrucciones desde el admin (chatbot_config).
    """
    if not LLM_ENABLED or not (GEMINI_API_KEY or "").strip():
        return None

    # Construir contexto de conversación reciente (para continuidad)
    conversation_block = ""
    if last_user_message and last_bot_message:
        conversation_block = (
            f"Intercambio anterior:\nUsuario: {last_user_message[:300]}\nAsistente: {last_bot_message[:400]}\n\n"
        )
    elif last_user_message:
        conversation_block = f"Último mensaje del usuario (contexto): {last_user_message[:300]}\n\n"

    data_block = ""
    if data_context and data_context.strip():
        data_block = f"{data_context.strip()}\n\n"

    base_instructions = (system_prompt or "").strip() or DEFAULT_SYSTEM_PROMPT

    prompt = (
        f"{base_instructions}\n\n"
        f"{conversation_block}"
        f"Mensaje actual del usuario: {user_message[:600]}\n\n"
        f"{data_block}"
        f"Borrador de respuesta (usa esta información, pero escribe de forma más conversacional y fluida):\n{draft_reply[:1800]}\n\n"
        "Escribe únicamente la respuesta final al usuario, sin explicaciones ni comillas."
    )

    payload = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {
            "temperature": 0.5,
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
        if not text or len(text) > 2500:
            return None
        return text
    except Exception as e:
        logger.warning("Célula inteligente (Gemini) falló: %s", e)
        return None


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
