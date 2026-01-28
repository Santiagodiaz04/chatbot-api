# main.py - API REST Chatbot Inmobiliario CTR
"""FastAPI. POST /chat, GET /health. CORS para frontend PHP."""

from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from config import CORS_ORIGINS, PHP_BASE_URL
from db import crear_conversacion, guardar_mensaje
from handlers import dispatch

app = FastAPI(
    title="Chatbot CTR Bienes Raíces",
    description="API del asistente inmobiliario. Complementa el backend PHP.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=CORS_ORIGINS if CORS_ORIGINS else ["*"],
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
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

    if not session_id:
        session_id = crear_conversacion(origen="web")

    try:
        out = dispatch(msg, contexto, session_id, PHP_BASE_URL)
    except Exception as e:
        raise HTTPException(status_code=500, detail="Error procesando mensaje")

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
