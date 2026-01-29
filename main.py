# main.py - API REST Chatbot Inmobiliario CTR
"""FastAPI. POST /chat, GET /health. CORS para frontend PHP."""

import logging
import uuid
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from config import CORS_ORIGINS, PHP_BASE_URL
from db import crear_conversacion, guardar_mensaje
from handlers import dispatch

logger = logging.getLogger("chatbot-api")

# Orígenes permitidos: lista explícita + dominio producción (siempre permitir ctrbienesraices.com)
ALLOWED_ORIGINS = list(CORS_ORIGINS) if CORS_ORIGINS else []
for o in ("https://ctrbienesraices.com", "https://www.ctrbienesraices.com", "http://ctrbienesraices.com", "http://www.ctrbienesraices.com"):
    if o not in ALLOWED_ORIGINS:
        ALLOWED_ORIGINS.append(o)
if not ALLOWED_ORIGINS:
    ALLOWED_ORIGINS = ["*"]


def _cors_allow_origin(origin: str) -> str:
    """Devuelve el origen a poner en Access-Control-Allow-Origin (nunca * si credentials)."""
    if not origin:
        return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS and "*" not in ALLOWED_ORIGINS else "*"
    origin = origin.rstrip("/")
    if "*" in ALLOWED_ORIGINS:
        return origin
    if origin in ALLOWED_ORIGINS:
        return origin
    # Permitir cualquier subdominio de ctrbienesraices.com
    if "ctrbienesraices.com" in origin and (origin.startswith("https://") or origin.startswith("http://")):
        return origin
    return ALLOWED_ORIGINS[0] if ALLOWED_ORIGINS else "*"


app = FastAPI(
    title="Chatbot CTR Bienes Raíces",
    description="API del asistente inmobiliario. Complementa el backend PHP.",
    version="1.0.0",
)


class CORSFixMiddleware(BaseHTTPMiddleware):
    """Responde OPTIONS con 200 y CORS; añade CORS a todas las respuestas."""

    async def dispatch(self, request: Request, call_next):
        origin = (request.headers.get("origin") or "").strip().rstrip("/")
        allow_origin = _cors_allow_origin(origin or request.headers.get("origin") or "")

        # Preflight: responder de inmediato con 200 y headers CORS
        if request.method == "OPTIONS":
            return JSONResponse(
                content={},
                status_code=200,
                headers={
                    "Access-Control-Allow-Origin": allow_origin,
                    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
                    "Access-Control-Allow-Headers": "Content-Type, Authorization, Accept, Origin",
                    "Access-Control-Max-Age": "86400",
                    "Access-Control-Allow-Credentials": "true",
                },
            )

        response = await call_next(request)
        response.headers["Access-Control-Allow-Origin"] = allow_origin
        response.headers["Access-Control-Allow-Credentials"] = "true"
        response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
        response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization, Accept, Origin"
        return response


app.add_middleware(CORSFixMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
    expose_headers=["*"],
)


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: Optional[str] = Field(None, max_length=64)
    contexto: Optional[Dict[str, Any]] = None
    referencia_tipo: Optional[str] = Field(None, pattern="^(propiedad|proyecto)$")
    referencia_id: Optional[int] = Field(None, ge=1)


class ChatResponse(BaseModel):
    text: str
    actions: List[Any] = []
    cards: Optional[List[Dict[str, Any]]] = None
    context: Dict[str, Any] = {}
    session_id: str
    intent: Optional[str] = None


@app.get("/health")
def health():
    """Health check para monitoreo."""
    return {"status": "ok", "service": "chatbot-api"}


def _fallback_response(session_id: str) -> ChatResponse:
    """Respuesta cuando falla la BD (ej: Railway no puede conectar a MySQL de Hostinger)."""
    return ChatResponse(
        text="En este momento no puedo conectar con la base de datos. Por favor intenta más tarde o contáctanos por teléfono al 316 569 4866.",
        actions=[],
        cards=None,
        context={"done": False},
        session_id=session_id,
        intent=None,
    )


@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest):
    """
    Recibe mensaje del usuario, detecta intención, responde.
    session_id: opcional; si no se envía, se crea nueva conversación.
    contexto: estado previo (nombre, teléfono, fecha, etc.).
    referencia_tipo / referencia_id: cuando el usuario elige "Agendar" en una card.
    """
    msg = (req.message or "").strip()
    if not msg:
        raise HTTPException(status_code=400, detail="message requerido")

    session_id = (req.session_id or "").strip() or None
    contexto = dict(req.contexto or {})

    if req.referencia_tipo and req.referencia_id:
        contexto["tipo_referencia"] = req.referencia_tipo
        contexto["referencia_id"] = req.referencia_id

    try:
        if not session_id:
            session_id = crear_conversacion(origen="web")
    except Exception as e:
        logger.exception("Error creando conversación (BD no accesible?): %s", e)
        session_id = str(uuid.uuid4()).replace("-", "")[:32]
        return _fallback_response(session_id)

    try:
        out = dispatch(msg, contexto, session_id, PHP_BASE_URL)
    except Exception as e:
        logger.exception("Error en dispatch: %s", e)
        return _fallback_response(session_id)

    text = (out.get("text") or "").strip()
    actions = out.get("actions") or []
    cards = out.get("cards")
    ctx = out.get("context") or {}
    intent = out.get("intent")

    try:
        guardar_mensaje(session_id, "user", msg)
        guardar_mensaje(session_id, "bot", text, metadata={"intent": intent, "cards": bool(cards)})
    except Exception:
        pass

    return ChatResponse(
        text=text,
        actions=actions,
        cards=cards,
        context=ctx,
        session_id=session_id,
        intent=intent,
    )
