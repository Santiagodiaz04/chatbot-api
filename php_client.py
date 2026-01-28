# php_client.py - Llamadas a APIs PHP (horarios, procesar cita)
"""Reutiliza lógica existente en PHP. No duplica validaciones ni emails."""

from typing import Any, Dict, List, Optional

import httpx

from config import PHP_BASE_URL


def _url(path: str) -> str:
    return f"{PHP_BASE_URL.rstrip('/')}{path}"


def horarios_disponibles(fecha: str) -> List[str]:
    """
    GET api/horarios-disponibles.php?fecha=YYYY-MM-DD
    Devuelve lista de horas ['08:30', '09:30', ...] o [].
    """
    try:
        r = httpx.get(_url("/api/horarios-disponibles.php"), params={"fecha": fecha}, timeout=10.0)
        r.raise_for_status()
        data = r.json()
        if isinstance(data, dict) and data.get("success") and "horarios" in data:
            return list(data["horarios"]) if isinstance(data["horarios"], (list, tuple)) else []
        return []
    except Exception:
        return []


def procesar_cita(
    nombre: str,
    telefono: str,
    tipo_referencia: str,
    referencia_id: int,
    fecha: str,
    hora: str,
    email: Optional[str] = None,
) -> Dict[str, Any]:
    """
    POST procesar-cita.php (form).
    Devuelve {success, message, cita_id?, agente?}.
    """
    payload: Dict[str, Any] = {
        "nombre": nombre.strip(),
        "telefono": telefono.strip(),
        "tipo_referencia": tipo_referencia,
        "referencia_id": referencia_id,
        "fecha": fecha,
        "hora": hora,
    }
    if email and email.strip():
        payload["email"] = email.strip()

    try:
        r = httpx.post(_url("/procesar-cita.php"), data=payload, timeout=15.0)
        r.raise_for_status()
        return r.json() if r.content else {"success": False, "message": "Respuesta vacía"}
    except httpx.HTTPStatusError as e:
        try:
            body = e.response.json()
        except Exception:
            body = {"message": e.response.text or str(e)}
        return {"success": False, "message": body.get("message", "Error al procesar la cita")}
    except Exception as e:
        return {"success": False, "message": "No se pudo conectar con el servidor. Intenta más tarde."}
