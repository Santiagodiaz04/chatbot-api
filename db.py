# db.py - Conexión MySQL para API Chatbot CTR
"""
Acceso a BD. Usa tablas: propiedades, proyectos, citas, agentes, chatbot_*.

Importante: cada petición al chat consulta la BD en vivo; no hay caché.
Cuando agregues o actualices una casa/proyecto en la BD, el bot la verá en la
siguiente consulta (si está activo=1 y estado='disponible' en propiedades).
"""

import uuid
from contextlib import contextmanager
from typing import Any, Generator, List, Optional

import mysql.connector
from mysql.connector import Error

from config import DB_CHARSET, DB_HOST, DB_NAME, DB_PASS, DB_PORT, DB_USER


def get_conn():
    """Conexión MySQL (misma BD que PHP)."""
    return mysql.connector.connect(
        host=DB_HOST,
        port=DB_PORT,
        database=DB_NAME,
        user=DB_USER,
        password=DB_PASS,
        charset=DB_CHARSET,
        collation="utf8mb4_unicode_ci",
        autocommit=False,
    )


@contextmanager
def cursor_dict():
    """Context manager: cursor con resultados como dict."""
    conn = get_conn()
    cur = conn.cursor(dictionary=True)
    try:
        yield cur
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


def config_get(key: str) -> Optional[str]:
    """Obtener valor de chatbot_config."""
    with cursor_dict() as cur:
        cur.execute("SELECT `value` FROM chatbot_config WHERE `key` = %s", (key,))
        row = cur.fetchone()
        return row["value"] if row else None


def faq_match(texto: str, limite: int = 5) -> List[dict]:
    """
    Buscar FAQs por coincidencia en pregunta o palabras_clave.
    Devuelve lista de {id, pregunta, respuesta, categoria}.
    """
    texto = (texto or "").strip().lower()
    if not texto or len(texto) < 2:
        return []
    words = [w.strip() for w in texto.split() if len(w.strip()) >= 2]
    if not words:
        return []

    with cursor_dict() as cur:
        cur.execute(
            """
            SELECT id, pregunta, respuesta, categoria, palabras_clave
            FROM chatbot_faqs
            WHERE activo = 1
            ORDER BY orden, id
            """,
        )
        rows = cur.fetchall()

    scored = []
    for r in rows:
        q = (r["pregunta"] or "").lower()
        kw = (r.get("palabras_clave") or "").lower()
        combined = f"{q} {kw}"
        score = sum(1 for w in words if w in combined)
        if score > 0:
            scored.append((score, r))
    scored.sort(key=lambda x: -x[0])
    return [r for _, r in scored[:limite]]


def buscar_propiedades(
    tipo: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    habitaciones: Optional[int] = None,
    ubicacion: Optional[str] = None,
    titulo: Optional[str] = None,
    proyecto_id: Optional[int] = None,
    exclude_ids: Optional[List[int]] = None,
    limite: int = 6,
) -> List[dict]:
    """
    Filtrar propiedades activas y disponibles. Consulta la BD en vivo (sin caché):
    cualquier casa nueva con activo=1 y estado='disponible' aparece de inmediato.
    tipo: venta | renta | lote
    ubicacion/titulo: búsqueda por ubicación o por nombre (titulo) de la propiedad.
    exclude_ids: excluir estos IDs (para "qué otra tienes").
    """
    q = """
        SELECT id, titulo, slug, tipo, ubicacion, precio, habitaciones, banos,
               area_construida, area_total, imagen_principal, descripcion
        FROM propiedades
        WHERE activo = 1 AND estado = 'disponible'
        """
    params: List[Any] = []
    if tipo:
        q += " AND tipo = %s"
        params.append(tipo)
    if precio_min is not None:
        q += " AND precio >= %s"
        params.append(precio_min)
    if precio_max is not None:
        q += " AND precio <= %s"
        params.append(precio_max)
    if habitaciones is not None:
        q += " AND habitaciones >= %s"
        params.append(habitaciones)
    if exclude_ids:
        placeholders = ", ".join(["%s"] * len(exclude_ids))
        q += f" AND id NOT IN ({placeholders})"
        params.extend(exclude_ids)
    if ubicacion and not titulo:
        q += " AND ubicacion LIKE %s"
        params.append(f"%{ubicacion.strip()}%")
    elif titulo and not ubicacion:
        q += " AND titulo LIKE %s"
        params.append(f"%{titulo.strip()}%")
    elif ubicacion and titulo:
        # Búsqueda por nombre o ubicación (ej. "qué es Ibiza"): coincide en cualquiera
        q += " AND (ubicacion LIKE %s OR titulo LIKE %s)"
        params.extend([f"%{ubicacion.strip()}%", f"%{titulo.strip()}%"])
    q += " ORDER BY destacado DESC, orden, id LIMIT %s"
    params.append(limite)

    with cursor_dict() as cur:
        cur.execute(q, params)
        return cur.fetchall()


def get_propiedad_by_id(propiedad_id: int) -> Optional[dict]:
    """Obtener una propiedad por ID (para preguntas de seguimiento: baños, detalles)."""
    with cursor_dict() as cur:
        cur.execute(
            """
            SELECT id, titulo, slug, tipo, ubicacion, precio, habitaciones, banos,
                   area_construida, area_total, imagen_principal, descripcion
            FROM propiedades
            WHERE activo = 1 AND estado = 'disponible' AND id = %s
            """,
            (propiedad_id,),
        )
        return cur.fetchone()


def buscar_proyectos(
    ubicacion: Optional[str] = None,
    limite: int = 6,
) -> List[dict]:
    """
    Proyectos activos. Consulta la BD en vivo (sin caché):
    proyectos nuevos con activo=1 aparecen de inmediato en el bot.
    Opcional filtro por ubicación.
    """
    q = """
        SELECT id, nombre, slug, ubicacion, precio_desde, imagen_principal, descripcion
        FROM proyectos
        WHERE activo = 1
        """
    params: List[Any] = []
    if ubicacion:
        q += " AND (ubicacion LIKE %s OR nombre LIKE %s)"
        params.extend([f"%{ubicacion}%", f"%{ubicacion}%"])
    q += " ORDER BY destacado DESC, orden, id LIMIT %s"
    params.append(limite)

    with cursor_dict() as cur:
        cur.execute(q, params)
        return cur.fetchall()


def crear_conversacion(origen: str = "web") -> str:
    """Crea conversación y devuelve id (UUID)."""
    cid = str(uuid.uuid4()).replace("-", "")[:32]
    with cursor_dict() as cur:
        cur.execute(
            "INSERT INTO chatbot_conversaciones (id, origen) VALUES (%s, %s)",
            (cid, origen),
        )
    return cid


def guardar_mensaje(conversacion_id: str, rol: str, contenido: str, metadata: Optional[dict] = None) -> None:
    """Guarda mensaje user/bot."""
    import json

    meta = json.dumps(metadata) if metadata else None
    with cursor_dict() as cur:
        cur.execute(
            "UPDATE chatbot_conversaciones SET fecha_ultimo_mensaje = CURRENT_TIMESTAMP WHERE id = %s",
            (conversacion_id,),
        )
        cur.execute(
            "INSERT INTO chatbot_mensajes (conversacion_id, rol, contenido, metadata_json) VALUES (%s, %s, %s, %s)",
            (conversacion_id, rol, contenido, meta),
        )


def marcar_conversion_cita(conversacion_id: str, cita_id: int) -> None:
    """Marcar conversación como conversión a cita."""
    with cursor_dict() as cur:
        cur.execute(
            "UPDATE chatbot_conversaciones SET conversion_cita = 1, cita_id = %s WHERE id = %s",
            (cita_id, conversacion_id),
        )


def log_pregunta(
    conversacion_id: Optional[str],
    texto_usuario: str,
    intent_detectado: Optional[str] = None,
    faq_id: Optional[int] = None,
) -> None:
    """Registrar pregunta para analytics y mejora."""
    with cursor_dict() as cur:
        cur.execute(
            """
            INSERT INTO chatbot_log_preguntas (conversacion_id, texto_usuario, intent_detectado, faq_id)
            VALUES (%s, %s, %s, %s)
            """,
            (conversacion_id, texto_usuario[:2000], intent_detectado, faq_id),
        )
