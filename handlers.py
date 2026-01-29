# handlers.py - Lógica de respuesta por intención
"""Saludo, búsqueda, info, agendar cita. Tono cercano y orientado a venta."""

from typing import Any, Dict, List, Optional

from db import (
    buscar_propiedades,
    buscar_proyectos,
    config_get,
    faq_match,
    log_pregunta,
    marcar_conversion_cita,
)
from nlu import (
    INTENT_AGENDAR_CITA,
    INTENT_BUSCAR_PROPIEDAD,
    INTENT_CONFIRMAR_DATOS,
    INTENT_DESPEDIDA,
    INTENT_DUDA_GENERAL,
    INTENT_PEDIR_INFORMACION,
    INTENT_SALUDO,
    detect_intent,
    extract_entities,
    extract_fecha,
    extract_hora,
    extract_nombre,
    extract_telefono,
    extract_email,
)
from php_client import horarios_disponibles, procesar_cita

try:
    from llm_client import generate_reply as llm_generate_reply
except ImportError:
    llm_generate_reply = None


def _cfg(key: str, default: str = "") -> str:
    return (config_get(key) or default).strip()


def _format_precio(v: Optional[float]) -> str:
    if v is None:
        return ""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M" if v % 1_000_000 == 0 else f"${v/1_000_000:.2f}M"
    return f"${v:,.0f}"


def _url_propiedad(slug: str, base: str) -> str:
    return f"{base.rstrip('/')}/?page=propiedad&slug={slug}"


def _url_proyecto(slug: str, base: str) -> str:
    return f"{base.rstrip('/')}/?page=proyecto&slug={slug}"


def handle_saludo(conversacion_id: Optional[str], base_url: str) -> Dict[str, Any]:
    msg = _cfg("saludo_inicial", "Hola, soy el asistente de CTR Bienes Raíces. Puedo mostrarte casas, apartamentos, lotes o en renta, y agendar visitas. ¿Qué buscas?")
    return {"text": msg, "actions": [], "context": {}}


def handle_despedida(conversacion_id: Optional[str], base_url: str) -> Dict[str, Any]:
    msg = _cfg("despedida", "Gracias por contactarnos. Cuando quieras, aquí estaré. ¡Que tengas un gran día! 🙂")
    return {"text": msg, "actions": [], "context": {"done": True}}


def handle_buscar_propiedad(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    ent = extract_entities(texto)
    tipo = ent.get("tipo") or contexto.get("tipo")
    precio_min = ent.get("presupuesto_min") or contexto.get("presupuesto_min")
    # Presupuesto máximo: respetar estrictamente (nunca mostrar más caro que lo indicado)
    precio_max = ent.get("presupuesto_max") or contexto.get("presupuesto_max")
    habitaciones = ent.get("habitaciones") if ent.get("habitaciones") is not None else contexto.get("habitaciones")
    ubicacion = (ent.get("ubicacion") or "").strip() or (contexto.get("ubicacion") or "").strip()

    props = buscar_propiedades(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max,
        habitaciones=habitaciones,
        ubicacion=ubicacion if ubicacion else None,
        limite=6,
    )
    proyectos = buscar_proyectos(ubicacion=ubicacion if ubicacion else None, limite=3)

    sale_msg = _cfg("mensaje_venta_propiedades", "Estas opciones podrían interesarte. ¿Quieres ver más detalles o agendar una visita?")
    urge_msg = _cfg("mensaje_urgencia", "Hay pocas con esas características; te conviene agendar pronto.")
    agenda_msg = _cfg("mensaje_agendar_cita", "¿Quieres agendar una visita? Te pido nombre, correo y teléfono para confirmar.")

    lines: List[str] = []
    cards: List[Dict[str, Any]] = []

    if props:
        if precio_max:
            lines.append(f"Encontré **{len(props)}** opción(es) dentro de tu presupuesto.")
        else:
            lines.append(f"Encontré **{len(props)}** propiedad(es) que encajan con lo que buscas.")
        for p in props[:4]:
            cards.append({
                "type": "propiedad",
                "id": p["id"],
                "titulo": p["titulo"],
                "tipo": p.get("tipo", "venta"),
                "ubicacion": p.get("ubicacion") or "",
                "precio": _format_precio(float(p["precio"])) if p.get("precio") else "",
                "habitaciones": p.get("habitaciones"),
                "url": _url_propiedad(p["slug"], base_url),
                "imagen": f"{base_url.rstrip('/')}/uploads/propiedades/{p['imagen_principal']}" if p.get("imagen_principal") else None,
            })
        if len(props) <= 2:
            lines.append(urge_msg)
        lines.append(sale_msg)
        lines.append(agenda_msg)
    elif proyectos:
        # Respetar presupuesto: no mostrar proyectos por encima del tope
        if precio_max is not None:
            proyectos = [pr for pr in proyectos if (pr.get("precio_desde") or 0) <= precio_max]
        if proyectos:
            lines.append(f"En proyectos encontré **{len(proyectos)}** opción(es).")
            for pr in proyectos[:3]:
                cards.append({
                    "type": "proyecto",
                    "id": pr["id"],
                    "titulo": pr["nombre"],
                    "ubicacion": pr.get("ubicacion") or "",
                    "precio_desde": _format_precio(float(pr["precio_desde"])) if pr.get("precio_desde") else "",
                    "url": _url_proyecto(pr["slug"], base_url),
                    "imagen": f"{base_url.rstrip('/')}/uploads/proyectos/{pr['imagen_principal']}" if pr.get("imagen_principal") else None,
                })
            lines.append(sale_msg)
            lines.append(agenda_msg)
        else:
            lines.append("No encontré proyectos dentro de ese presupuesto. ¿Ajustamos el rango o prefieres que te muestre propiedades?")
            lines.append(agenda_msg)
    else:
        if precio_max:
            lines.append(f"No encontré propiedades dentro de ese presupuesto. ¿Ajustamos el rango o te muestro opciones un poco más altas? También puedo agendar una visita para que un asesor te ayude.")
        else:
            lines.append("No encontré propiedades con esos criterios. ¿Ajustamos filtros (presupuesto, habitaciones, zona) o prefieres que te muestre opciones generales?")
        lines.append(agenda_msg)

    ctx = {
        "tipo": tipo,
        "presupuesto_min": precio_min,
        "presupuesto_max": precio_max,
        "habitaciones": habitaciones,
        "ubicacion": ubicacion or None,
    }
    return {"text": "\n\n".join(lines), "actions": [], "cards": cards, "context": ctx}


def handle_pedir_informacion(
    texto: str,
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    faqs = faq_match(texto, limite=3)
    if faqs:
        r = faqs[0]
        msg = r["respuesta"]
        log_pregunta(conversacion_id, texto, "pedir_informacion", r["id"])
        return {"text": msg, "actions": [], "context": {}}

    t = (texto or "").lower()
    # Preguntas sobre detalles (garaje, servicios, requisitos, lotes): respuesta natural si no hay FAQ
    if any(w in t for w in ["garaje", "garage", "parqueadero", "servicios incluidos", "incluye", "requisitos", "documentos", "lote", "lotes"]):
        msg = "Ese detalle no lo tengo a mano aquí, pero un asesor te puede dar toda la información. ¿Quieres que te muestre opciones disponibles o prefieres agendar una visita?"
        return {"text": msg, "actions": [], "context": {}}

    msg = "Puedo ayudarte con propiedades (venta, renta, lotes), proyectos, horarios o agendar visitas. ¿Qué te gustaría saber?"
    return {"text": msg, "actions": [], "context": {}}


def handle_agendar_cita(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    esperando = contexto.get("esperando")
    nombre = contexto.get("nombre") or extract_nombre(texto)
    email = contexto.get("email") or extract_email(texto)
    telefono = contexto.get("telefono") or extract_telefono(texto)
    tipo_ref = contexto.get("tipo_referencia")
    ref_id = contexto.get("referencia_id")
    fecha = contexto.get("fecha_cita") or extract_fecha(texto)
    hora = contexto.get("hora_cita") or extract_hora(texto)

    if esperando == "nombre" and nombre:
        contexto["nombre"] = nombre
        contexto["esperando"] = "email"
        return {"text": "Gracias. ¿Cuál es tu correo electrónico? (para enviarte la confirmación)", "actions": [], "context": contexto}
    if esperando == "email":
        em = extract_email(texto) or (texto.strip() if "@" in texto else None)
        if em:
            contexto["email"] = em
            contexto["esperando"] = "telefono"
            return {"text": "Perfecto. ¿En qué número te contacto? (celular)", "actions": [], "context": contexto}
        return {"text": "Por favor escribe tu correo (ej. nombre@correo.com) para enviarte la confirmación de la cita.", "actions": [], "context": contexto}
    if esperando == "telefono":
        tel = extract_telefono(texto)
        if tel:
            contexto["telefono"] = tel
            contexto["esperando"] = None
            # Tenemos nombre + tel. Si hay referencia y horario, intentar agendar. Si no, pedir fecha/hora o referencia.
            if tipo_ref and ref_id and fecha and hora:
                return _do_procesar_cita(contexto, conversacion_id, base_url)
            if tipo_ref and ref_id:
                contexto["esperando"] = "fecha"
                return {"text": "¿Qué fecha te queda bien? (formato: AAAA-MM-DD, ej. 2025-02-15)", "actions": [], "context": contexto}
            # Sin referencia: pedir que elija de las opciones o agendar “visita general”
            contexto["esperando"] = "fecha"
            return {"text": "¿Qué fecha te gustaría? (formato: AAAA-MM-DD)", "actions": [], "context": contexto}
        return {"text": "Escribe tu número de celular (ej. 3001234567) para confirmar la visita.", "actions": [], "context": contexto}

    if not nombre:
        contexto["esperando"] = "nombre"
        return {"text": _cfg("mensaje_agendar_cita", "Para agendar la visita necesito algunos datos. ¿Cuál es tu nombre?") + "\n\n(Después te pediré correo y teléfono para la confirmación.)", "actions": [], "context": contexto}
    if not email:
        contexto["nombre"] = nombre
        contexto["esperando"] = "email"
        return {"text": "¿Cuál es tu correo? Así te enviamos la confirmación de la cita.", "actions": [], "context": contexto}
    if not telefono:
        contexto["nombre"] = nombre
        contexto["email"] = email
        contexto["esperando"] = "telefono"
        return {"text": "¿En qué número te contacto? (celular)", "actions": [], "context": contexto}

    if not fecha:
        contexto["nombre"] = nombre
        contexto["email"] = email
        contexto["telefono"] = telefono
        contexto["esperando"] = "fecha"
        return {"text": "¿Qué fecha te queda bien? (formato: AAAA-MM-DD)", "actions": [], "context": contexto}
    if not hora:
        horas = horarios_disponibles(fecha)
        if not horas:
            return {"text": "Ese día no hay horarios disponibles. ¿Pruebas otra fecha? (AAAA-MM-DD)", "actions": [], "context": {**contexto, "fecha_cita": None}}
        contexto["fecha_cita"] = fecha
        contexto["esperando"] = "hora"
        return {"text": f"Horarios disponibles: {', '.join(horas[:10])}. ¿Cuál prefieres?", "actions": [{"type": "horarios", "horarios": horas}], "context": contexto}

    horas_ok = horarios_disponibles(fecha)
    if horas_ok and hora not in horas_ok:
        return {"text": f"Ese horario no está disponible. Opciones: {', '.join(horas_ok[:10])}. ¿Cuál prefieres?", "actions": [{"type": "horarios", "horarios": horas_ok}], "context": contexto}
    contexto["hora_cita"] = hora
    return _do_procesar_cita(contexto, conversacion_id, base_url)


def _do_procesar_cita(contexto: Dict[str, Any], conversacion_id: Optional[str], base_url: str) -> Dict[str, Any]:
    nombre = (contexto.get("nombre") or "").strip()
    telefono = (contexto.get("telefono") or "").strip()
    email = (contexto.get("email") or "").strip() or None
    tipo = (contexto.get("tipo_referencia") or "proyecto").strip()
    ref_id = int(contexto.get("referencia_id") or 0)
    fecha = (contexto.get("fecha_cita") or "").strip()
    hora = (contexto.get("hora_cita") or "").strip()

    if not nombre or not telefono or not fecha or not hora:
        return {"text": "Faltan datos para confirmar la cita. ¿Tu nombre y teléfono?", "actions": [], "context": {**contexto, "esperando": "nombre"}}

    if tipo not in ("propiedad", "proyecto") or ref_id <= 0:
        tipo = "proyecto"
        # Elegir primer proyecto activo como referencia “visita general”
        proy = buscar_proyectos(limite=1)
        if proy:
            ref_id = proy[0]["id"]
            tipo = "proyecto"
        else:
            prop = buscar_propiedades(limite=1)
            if prop:
                ref_id = prop[0]["id"]
                tipo = "propiedad"
            else:
                return {"text": "No hay propiedades o proyectos disponibles para agendar. Escríbenos por teléfono y te ayudamos.", "actions": [], "context": {}}

    resp = procesar_cita(nombre=nombre, telefono=telefono, tipo_referencia=tipo, referencia_id=ref_id, fecha=fecha, hora=hora, email=email)
    if resp.get("success") and resp.get("cita_id"):
        if conversacion_id:
            marcar_conversion_cita(conversacion_id, int(resp["cita_id"]))
        agente = resp.get("agente", "un asesor")
        return {"text": f"¡Listo! 📅 Tu cita quedó agendada. {agente} te estará esperando. Cualquier cambio, escríbenos.", "actions": [], "context": {"done": True, "cita_id": resp["cita_id"]}}
    return {"text": resp.get("message", "No pude agendar la cita. Intenta de nuevo o escríbenos por teléfono."), "actions": [], "context": contexto}


def handle_duda_general(texto: str, conversacion_id: Optional[str], base_url: str) -> Dict[str, Any]:
    faqs = faq_match(texto, limite=2)
    if faqs:
        msg = faqs[0]["respuesta"]
        log_pregunta(conversacion_id, texto, "duda_general", faqs[0]["id"])
        return {"text": msg, "actions": [], "context": {}}
    t = (texto or "").lower()
    if any(w in t for w in ["garaje", "garage", "servicios", "requisitos", "lote", "lotes", "renta", "arriendo"]):
        return {"text": "Ese dato no lo tengo aquí; un asesor te puede contar todo. ¿Te muestro opciones o agendamos una visita?", "actions": [], "context": {}}
    return {"text": "¿En qué te ayudo? Puedo mostrarte propiedades (venta, renta, lotes), proyectos o agendar una visita.", "actions": [], "context": {}}


def handle_confirmar_datos(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    return handle_agendar_cita(texto, contexto, conversacion_id, base_url)


def dispatch(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    intent = detect_intent(texto, contexto)
    handlers = {
        INTENT_SALUDO: lambda: handle_saludo(conversacion_id, base_url),
        INTENT_DESPEDIDA: lambda: handle_despedida(conversacion_id, base_url),
        INTENT_BUSCAR_PROPIEDAD: lambda: handle_buscar_propiedad(texto, contexto, conversacion_id, base_url),
        INTENT_PEDIR_INFORMACION: lambda: handle_pedir_informacion(texto, conversacion_id, base_url),
        INTENT_AGENDAR_CITA: lambda: handle_agendar_cita(texto, contexto, conversacion_id, base_url),
        INTENT_CONFIRMAR_DATOS: lambda: handle_confirmar_datos(texto, contexto, conversacion_id, base_url),
        INTENT_DUDA_GENERAL: lambda: handle_duda_general(texto, conversacion_id, base_url),
    }
    h = handlers.get(intent, lambda: handle_duda_general(texto, conversacion_id, base_url))
    out = h()
    if "context" not in out:
        out["context"] = {}

    # IA opcional: humanizar el texto (cards, actions y context no cambian)
    if llm_generate_reply and out.get("text"):
        try:
            natural = llm_generate_reply(texto, out["text"], intent)
            if natural:
                out["text"] = natural
        except Exception:
            pass

    out["intent"] = intent
    return out
