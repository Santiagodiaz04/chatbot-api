# nlu.py - Detección de intención y extracción de entidades
"""Reglas y keywords. Escalable a ML/NLP después."""

import re
from typing import Any, Dict, List, Optional, Tuple

# Intenciones soportadas
INTENT_SALUDO = "saludo"
INTENT_BUSCAR_PROPIEDAD = "buscar_propiedad"
INTENT_PEDIR_INFORMACION = "pedir_informacion"
INTENT_AGENDAR_CITA = "agendar_cita"
INTENT_DUDA_GENERAL = "duda_general"
INTENT_DESPEDIDA = "despedida"
INTENT_CONFIRMAR_DATOS = "confirmar_datos"  # nombre, teléfono para cita

# Keywords por intención (minúsculas)
KEYWORDS_SALUDO = [
    "hola", "buenas", "buenos dias", "buenas tardes", "buenas noches",
    "hey", "hi", "hello", "qué tal", "que tal", "saludos", "buen dia",
]
KEYWORDS_BUSCAR = [
    "busco", "buscar", "busco propiedad", "propiedad", "propiedades",
    "casa", "apartamento", "aparto", "lote", "venta", "renta", "arriendo",
    "cuánto", "cuanto", "precio", "presupuesto", "habitaciones", "alcobas",
    "baños", "banos", "ubicación", "ubicacion", "zona", "ciudad", "donde",
    "proyecto", "proyectos", "opciones", "disponibles", "hay", "tienen",
]
KEYWORDS_AGENDAR = [
    "agendar", "cita", "visita", "ver", "conocer", "conocer la propiedad",
    "conocer el proyecto", "quiero ver", "quiero visitar", "reservar",
    "cuando puedo", "horario", "fecha", "hora",
]
KEYWORDS_INFO = [
    "información", "informacion", "info", "saber", "contar", "cuéntame",
    "cuentame", "cómo", "como", "qué", "que", "donde", "dónde",
    "horario", "horarios", "ubicación", "ubicacion", "contacto", "teléfono",
    "telefono", "financiación", "financiacion", "cuotas", "requisitos",
]
KEYWORDS_DESPEDIDA = [
    "gracias", "chao", "adiós", "adios", "hasta luego", "bye", "nos vemos",
    "eso es todo", "nada más", "nada mas", "hasta pronto",
]

# Patrones para extraer entidades
RE_MONEDA = re.compile(
    r"(?:(\d[\d\s.,]*)\s*(?:millones?|millon|m|mm|mmdd|mmd)?|"
    r"(?:hasta|máximo|maximo|menos de)\s*(\d[\d\s.,]*)\s*(?:millones?|m)?)",
    re.I,
)
RE_NUMERO = re.compile(r"\b(\d{1,3})\s*(?:habitaciones?|alcobas?|baños?|banos?|cuartos?)\b", re.I)
RE_TIPO = re.compile(r"\b(venta|renta|arriendo|lote|casa|apartamento|aparto)\b", re.I)
RE_UBICACION = re.compile(
    r"(?:en|de|por|zona|sector|barrio|ciudad)\s+([a-zA-ZáéíóúÁÉÍÓÚñÑ\s\-]{2,40})"
    r"|(prado|centro|norte|sur|occidente|oriente|cali|bogotá|bogota|medellín|medellin|pereira|armenia)\b",
    re.I,
)


def _normalize(s: str) -> str:
    if not s:
        return ""
    t = s.lower().strip()
    t = re.sub(r"\s+", " ", t)
    return t


def _match_keywords(texto: str, keywords: List[str]) -> bool:
    t = _normalize(texto)
    for k in keywords:
        if k in t:
            return True
    return False


def detect_intent(texto: str, contexto: Optional[Dict[str, Any]] = None) -> str:
    """
    Detecta intención predominante.
    contexto: { "esperando": "nombre"|"telefono"|"fecha"|"hora"|None, "tipo_ref", "ref_id", ... }
    """
    t = _normalize(texto)
    if not t or len(t) < 2:
        return INTENT_DUDA_GENERAL

    ctx = contexto or {}
    esperando = ctx.get("esperando")

    if esperando == "nombre":
        return INTENT_CONFIRMAR_DATOS
    if esperando == "telefono":
        return INTENT_CONFIRMAR_DATOS
    if esperando == "fecha":
        return INTENT_AGENDAR_CITA
    if esperando == "hora":
        return INTENT_AGENDAR_CITA

    if _match_keywords(t, KEYWORDS_SALUDO) and len(t) < 60:
        return INTENT_SALUDO
    if _match_keywords(t, KEYWORDS_DESPEDIDA):
        return INTENT_DESPEDIDA
    if _match_keywords(t, KEYWORDS_AGENDAR) or "agendar" in t or "visita" in t or "cita" in t:
        return INTENT_AGENDAR_CITA
    if _match_keywords(t, KEYWORDS_BUSCAR):
        return INTENT_BUSCAR_PROPIEDAD
    if _match_keywords(t, KEYWORDS_INFO):
        return INTENT_PEDIR_INFORMACION

    # Preguntas cortas tipo "¿tienen X?" -> info o búsqueda
    if "tienen" in t or "hay" in t:
        return INTENT_BUSCAR_PROPIEDAD if any(w in t for w in ["propiedad", "casa", "aparto", "proyecto", "venta", "renta"]) else INTENT_PEDIR_INFORMACION

    return INTENT_DUDA_GENERAL


def extract_entities(texto: str) -> Dict[str, Any]:
    """
    Extrae presupuesto, habitaciones, tipo, ubicación.
    Devuelve dict con keys: presupuesto_min, presupuesto_max, habitaciones, tipo, ubicacion.
    """
    t = _normalize(texto)
    out: Dict[str, Any] = {
        "presupuesto_min": None,
        "presupuesto_max": None,
        "habitaciones": None,
        "tipo": None,
        "ubicacion": None,
    }

    # Tipo (prioridad: renta > lote > venta)
    for m in RE_TIPO.finditer(t):
        v = m.group(1).lower()
        if v in ("renta", "arriendo"):
            out["tipo"] = "renta"
            break
        if v == "lote":
            out["tipo"] = "lote"
            break
        if v in ("venta", "casa", "apartamento", "aparto"):
            out["tipo"] = "venta"
            break
    if not out["tipo"]:
        if "renta" in t or "arriendo" in t:
            out["tipo"] = "renta"
        elif "lote" in t:
            out["tipo"] = "lote"
        elif "venta" in t or "comprar" in t:
            out["tipo"] = "venta"

    # Habitaciones
    for m in RE_NUMERO.finditer(t):
        n = int(m.group(1))
        if 1 <= n <= 10:
            out["habitaciones"] = n
            break
    if out["habitaciones"] is None:
        for w in ("una habitacion", "1 habitacion", "dos habitaciones", "2 alcobas", "tres cuartos", "3 cuartos"):
            if w in t:
                out["habitaciones"] = 1 if "una" in w or "1" in w else (2 if "dos" in w or "2" in w else 3)
                break

    # Presupuesto: números + "millones" / "m" / "mm"
    def _parse_millions(s: str) -> Optional[float]:
        s = re.sub(r"[\s.]", "", s.replace(",", "."))
        try:
            v = float(s)
            if v < 1000:
                return v  # asumir millones
            return v / 1_000_000
        except Exception:
            return None

    for m in RE_MONEDA.finditer(t):
        g1, g2 = m.group(1), m.group(2) if m.lastindex and m.lastindex >= 2 else None
        for g in (g1, g2):
            if g:
                v = _parse_millions(g)
                if v and v > 0:
                    if "maximo" in t or "menos" in t or "hasta" in t:
                        out["presupuesto_max"] = v * 1_000_000
                    else:
                        out["presupuesto_min"] = out["presupuesto_min"] or v * 1_000_000
                    break
    # Palabras sueltas
    if "millon" in t or "millones" in t:
        for n in re.finditer(r"\b(\d{1,3}(?:[.,]\d+)?)\s*(?:millones?|m\b)?", t):
            v = _parse_millions(n.group(1))
            if v and v > 0:
                val = v * 1_000_000
                if out["presupuesto_max"] is None:
                    out["presupuesto_max"] = val
                if out["presupuesto_min"] is None:
                    out["presupuesto_min"] = val
                break

    # Ubicación
    for m in RE_UBICACION.finditer(t):
        u = (m.group(1) or m.group(2) or "").strip()
        if len(u) >= 2:
            out["ubicacion"] = u
            break
    if not out["ubicacion"]:
        for w in ("prado", "centro", "norte", "cali", "bogota", "medellin", "pereira", "armenia"):
            if w in t:
                out["ubicacion"] = w.capitalize()
                break

    return out


def extract_nombre(texto: str) -> Optional[str]:
    """Extrae nombre (frase simple, sin números)."""
    t = (texto or "").strip()
    t = re.sub(r"\s+", " ", t)
    if len(t) < 2 or len(t) > 120:
        return None
    if re.search(r"\d{5,}", t):
        return None
    return t if t else None


def extract_telefono(texto: str) -> Optional[str]:
    """Extrae teléfono (dígitos, posiblemente con espacios/guiones)."""
    digits = re.sub(r"\D", "", (texto or ""))
    if 7 <= len(digits) <= 15:
        return digits
    return None


def extract_fecha(texto: str) -> Optional[str]:
    """YYYY-MM-DD si detecta fecha en texto."""
    # ISO
    m = re.search(r"\b(20\d{2})-(\d{2})-(\d{2})\b", texto or "")
    if m:
        return m.group(0)
    # dd/mm/yyyy o dd-mm-yyyy
    m = re.search(r"\b(\d{1,2})[/\-](\d{1,2})[/\-](20\d{2})\b", texto or "")
    if m:
        d, mo, y = m.group(1).zfill(2), m.group(2).zfill(2), m.group(3)
        return f"{y}-{mo}-{d}"
    return None


def extract_hora(texto: str) -> Optional[str]:
    """HH:MM o HH:MM:SS."""
    m = re.search(r"\b(\d{1,2}):(\d{2})(?::(\d{2}))?\b", texto or "")
    if m:
        h, mi = int(m.group(1)), int(m.group(2))
        if 0 <= h <= 23 and 0 <= mi <= 59:
            return f"{h:02d}:{mi:02d}"
    return None
