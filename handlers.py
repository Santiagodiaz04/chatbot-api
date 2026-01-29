# handlers.py - Lógica de respuesta por intención
"""
Flujo: ENTENDER → CONSULTAR (BD) → RAZONAR → PERSUADIR.
Motor de razonamiento integrado; tono de secretaria experta.
"""

from typing import Any, Dict, List, Optional

from db import (
    buscar_propiedades,
    buscar_proyectos,
    config_get,
    faq_match,
    get_propiedad_by_id,
    log_pregunta,
    marcar_conversion_cita,
)
from nlu import (
    INTENT_AGENDAR_CITA,
    INTENT_BUSCAR_PROPIEDAD,
    INTENT_COMPARAR_OPCIONES,
    INTENT_CONFIRMAR_DATOS,
    INTENT_DESPEDIDA,
    INTENT_DUDA_GENERAL,
    INTENT_PEDIR_INFORMACION,
    INTENT_PEDIR_OTRA_OPCION,
    INTENT_PEDIR_RECOMENDACION,
    INTENT_PREGUNTA_SOBRE_PROPIEDAD,
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
from reasoning import run_reasoning

try:
    from llm_client import build_data_context, generate_reply as llm_generate_reply
except ImportError:
    llm_generate_reply = None
    build_data_context = None


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
    precio_max = ent.get("presupuesto_max") or contexto.get("presupuesto_max")
    habitaciones = ent.get("habitaciones") if ent.get("habitaciones") is not None else contexto.get("habitaciones")
    ubicacion = (ent.get("ubicacion") or "").strip() or (contexto.get("ubicacion") or "").strip()
    pide_proyectos = "proyecto" in (texto or "").lower()

    match_type, props, proyectos, reasoning_text = run_reasoning(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max,
        habitaciones=habitaciones,
        ubicacion=ubicacion or None,
        pide_proyectos=pide_proyectos,
    )

    agenda_msg = _cfg("mensaje_agendar_cita", "¿Quieres agendar una visita? Te pido nombre, correo y teléfono para confirmar.")
    cards: List[Dict[str, Any]] = []
    for p in props[:4]:
        cards.append(_card_propiedad(p, base_url))
    for pr in proyectos[:3]:
        if precio_max is None or (pr.get("precio_desde") or 0) <= (precio_max or 0):
            cards.append(_card_proyecto(pr, base_url))

    lines = [reasoning_text]
    if cards:
        lines.append(agenda_msg)

    ctx = {
        "tipo": tipo,
        "presupuesto_min": precio_min,
        "presupuesto_max": precio_max,
        "habitaciones": habitaciones,
        "ubicacion": ubicacion or None,
    }
    # Guardar la primera propiedad mostrada para preguntas de seguimiento ("cuántos baños tiene", "qué otra tienes")
    if props:
        ctx["tipo_referencia"] = "propiedad"
        ctx["referencia_id"] = props[0]["id"]
        ctx["propiedades_mostradas_ids"] = [p["id"] for p in props[:4]]
    if proyectos and not props:
        ctx["tipo_referencia"] = "proyecto"
        ctx["referencia_id"] = proyectos[0]["id"]
    return {"text": "\n\n".join(lines), "actions": [], "cards": cards, "context": ctx}


def _card_propiedad(p: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    return {
        "type": "propiedad",
        "id": p["id"],
        "titulo": p["titulo"],
        "tipo": p.get("tipo", "venta"),
        "ubicacion": p.get("ubicacion") or "",
        "precio": _format_precio(float(p["precio"])) if p.get("precio") else "",
        "habitaciones": p.get("habitaciones"),
        "banos": p.get("banos"),
        "descripcion": (p.get("descripcion") or "").strip(),
        "url": _url_propiedad(p["slug"], base_url),
        "imagen": f"{base_url.rstrip('/')}/uploads/propiedades/{p['imagen_principal']}" if p.get("imagen_principal") else None,
    }


def _card_proyecto(pr: Dict[str, Any], base_url: str) -> Dict[str, Any]:
    return {
        "type": "proyecto",
        "id": pr["id"],
        "titulo": pr["nombre"],
        "ubicacion": pr.get("ubicacion") or "",
        "precio_desde": _format_precio(float(pr["precio_desde"])) if pr.get("precio_desde") else "",
        "descripcion": (pr.get("descripcion") or "").strip(),
        "url": _url_proyecto(pr["slug"], base_url),
        "imagen": f"{base_url.rstrip('/')}/uploads/proyectos/{pr['imagen_principal']}" if pr.get("imagen_principal") else None,
    }


def _add_opciones_cercanas_or_fallback(
    tipo: Optional[str],
    precio_min: Optional[float],
    precio_max: Optional[float],
    habitaciones: Optional[int],
    ubicacion: Optional[str],
    lines: List[str],
    cards: List[Dict[str, Any]],
    base_url: str,
    agenda_msg: str,
    sale_msg: str,
) -> None:
    """
    Si no hay coincidencia exacta, busca opciones más cercanas (menos habitaciones,
    o un poco más de presupuesto) y responde de forma conversacional.
    """
    # Relajar filtros: 1 hab menos, o precio hasta +20% si dio presupuesto
    hab_relajado = (habitaciones - 1) if habitaciones and habitaciones > 1 else None
    precio_max_relajado = (precio_max * 1.2) if precio_max else None

    props_cercanas = buscar_propiedades(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max_relajado,
        habitaciones=hab_relajado,
        ubicacion=ubicacion,
        titulo=ubicacion,
        limite=6,
    )

    if props_cercanas:
        # Opciones más cercanas: mensaje adaptado a lo que pidió el usuario
        partes = []
        if habitaciones and precio_max:
            partes.append(f"De momento no tenemos exactamente {habitaciones} habitaciones dentro de ese presupuesto.")
        elif habitaciones:
            partes.append(f"De momento no tenemos una con exactamente {habitaciones} habitaciones.")
        elif precio_max:
            partes.append("No encontré propiedades dentro de ese presupuesto.")
        else:
            partes.append("No encontré propiedades con esas características.")
        partes.append("Aquí van las **opciones más cercanas** que sí tenemos:")
        lines.append(" ".join(partes))
        for p in props_cercanas[:4]:
            cards.append(_card_propiedad(p, base_url))
        # Resumen breve: ej. "Por ejemplo: 4 hab por $320M"
        ejemplos = []
        for p in props_cercanas[:2]:
            hab = p.get("habitaciones")
            prec = _format_precio(float(p["precio"])) if p.get("precio") else ""
            if hab and prec:
                ejemplos.append(f"{hab} hab por {prec}")
        if ejemplos:
            lines.append("Por ejemplo: " + ", ".join(ejemplos) + ".")
        lines.append("¿Te sirve alguna o preferimos ajustar (más habitaciones, otro rango)? También puedo agendar una visita con un asesor.")
        lines.append(agenda_msg)
        return

    # Sin opciones cercanas: búsqueda muy amplia (solo tipo, ubicación y nombre)
    props_general = buscar_propiedades(
        tipo=tipo,
        precio_min=None,
        precio_max=None,
        habitaciones=None,
        ubicacion=ubicacion,
        titulo=ubicacion,
        limite=4,
    )
    if props_general:
        lines.append("No tenemos justo lo que buscas, pero aquí van **otras opciones** que podrían interesarte:")
        for p in props_general[:4]:
            cards.append(_card_propiedad(p, base_url))
        lines.append("¿Ajustamos criterios o agendamos una visita para que un asesor te ayude?")
        lines.append(agenda_msg)
        return

    # Nada en BD: mensaje según si mencionó presupuesto o no
    if precio_max:
        lines.append("No encontré propiedades dentro de ese presupuesto. ¿Ajustamos el rango o te muestro opciones un poco más altas? También puedo agendar una visita para que un asesor te ayude.")
    else:
        lines.append("Por ahora no tenemos propiedades con esos criterios. ¿Quieres que ajustemos (habitaciones, zona, tipo) o prefieres que agende una visita con un asesor?")
    lines.append(agenda_msg)


def _extract_lugar_info(texto: str) -> Optional[str]:
    """
    Extrae nombre de proyecto/propiedad o lugar de frases como:
    'información de Ibiza', 'qué es Ibiza', 'que es Ibiza', 'hablame de X', 'info de X'.
    Sirve para buscar por nombre (ej. proyecto Ibiza) o ubicación.
    """
    if not texto or len(texto.strip()) < 3:
        return None
    t = (texto or "").strip().lower()
    # "información de X", "info de X", "qué hay en X"
    for prefix in ["informacion de ", "información de ", "info de ", "todo de ", "datos de ", "qué hay en ", "que hay en ", "hablame de ", "cuéntame de ", "cuentame de ", "hablar de ", "contar de "]:
        if prefix in t:
            resto = t.split(prefix, 1)[-1].strip()
            term = (resto.split()[0] if resto else "").strip(".,;:?!")
            if term and len(term) >= 2:
                return term
    # "qué es Ibiza", "que es Ibiza", "qué es el Ibiza", "qué es la Ibiza"
    for prefix in ["qué es ", "que es ", "q es ", "qué es el ", "que es el ", "qué es la ", "que es la "]:
        if t.startswith(prefix):
            resto = t[len(prefix):].strip().strip(".,;:?!")
            term = resto.split()[0] if resto else ""
            if term and len(term) >= 2:
                return term
    return None


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
    # "Información de [lugar]" (ej. Ibiza): buscar en BD y mostrar propiedades/proyectos con imágenes
    lugar = _extract_lugar_info(texto)
    if lugar:
        # Buscar por nombre (titulo/nombre) y por ubicación para "qué es Ibiza", "info de X", etc.
        props = buscar_propiedades(ubicacion=lugar, titulo=lugar, limite=6)
        proyectos = buscar_proyectos(ubicacion=lugar, limite=4)
        lines = []
        cards = []
        if props or proyectos:
            if props:
                lines.append(f"En **{lugar}** tenemos estas propiedades:")
                for p in props[:4]:
                    cards.append(_card_propiedad(p, base_url))
            if proyectos:
                lines.append(f"Y estos proyectos en **{lugar}**:")
                for pr in proyectos[:3]:
                    cards.append(_card_proyecto(pr, base_url))
            lines.append("¿Quieres más detalles de alguna o agendar una visita?")
            agenda_msg = _cfg("mensaje_agendar_cita", "¿Quieres agendar una visita? Te pido nombre, correo y teléfono para confirmar.")
            lines.append(agenda_msg)
            return {"text": "\n\n".join(lines), "actions": [], "cards": cards, "context": {"ubicacion": lugar}}
        lines.append(f"No encontré propiedades ni proyectos con ese nombre. ¿Buscas en otra zona o quieres que te muestre opciones generales?")
        return {"text": "\n\n".join(lines), "actions": [], "cards": [], "context": {}}

    # Ubicación / quiénes somos: usar config si no hay FAQ (preguntas rápidas y sencillas)
    if any(w in t for w in ["donde", "ubicados", "ubicacion", "ubicación", "direccion", "dirección"]):
        msg = _cfg("respuesta_ubicacion") or _cfg("ubicacion") or "Puedes ver nuestra ubicación y datos de contacto en la web. ¿Quieres que te muestre propiedades o agendar una visita?"
        return {"text": msg, "actions": [], "context": {}}
    if any(w in t for w in ["quienes somos", "quienes son", "que somos", "ctr bienes"]):
        msg = _cfg("respuesta_quienes_somos") or _cfg("quienes_somos") or "Somos CTR Bienes Raíces. Te ayudamos con propiedades en venta, renta y lotes. ¿Quieres ver opciones o agendar una visita?"
        return {"text": msg, "actions": [], "context": {}}
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
    # Guardar fecha/hora en contexto si el usuario dijo "mañana 8 am" etc., para no perderlas
    if fecha:
        contexto["fecha_cita"] = fecha
    if hora:
        contexto["hora_cita"] = hora

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
    if any(w in t for w in ["donde", "ubicados", "ubicacion", "ubicación", "direccion", "dirección"]):
        msg = _cfg("respuesta_ubicacion") or _cfg("ubicacion") or "Puedes ver nuestra ubicación y contacto en la web. ¿Quieres que te muestre propiedades o agendar una visita?"
        return {"text": msg, "actions": [], "context": {}}
    if any(w in t for w in ["quienes somos", "quienes son", "que somos", "ctr bienes"]):
        msg = _cfg("respuesta_quienes_somos") or _cfg("quienes_somos") or "Somos CTR Bienes Raíces. Te ayudamos con propiedades en venta, renta y lotes. ¿Quieres ver opciones o agendar una visita?"
        return {"text": msg, "actions": [], "context": {}}
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


def handle_pregunta_sobre_propiedad(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    """
    Responde preguntas sobre la propiedad mostrada: cuántos baños tiene, qué más tiene, etc.
    Contexto debe tener tipo_referencia y referencia_id (propiedad).
    """
    tipo_ref = contexto.get("tipo_referencia")
    ref_id = contexto.get("referencia_id")
    if tipo_ref != "propiedad" or not ref_id:
        return handle_duda_general(texto, conversacion_id, base_url)

    prop = get_propiedad_by_id(int(ref_id))
    if not prop:
        return {"text": "Esa propiedad ya no está disponible. ¿Quieres que te muestre otras opciones?", "actions": [], "context": {}}

    t = (texto or "").lower()
    lines: List[str] = []
    # Pregunta por baños
    if "baño" in t or "bano" in t or "baños" in t or "banos" in t:
        banos = prop.get("banos")
        if banos is not None:
            lines.append(f"Sí, tiene {banos} baño(s).")
        else:
            lines.append("Ese dato no lo tengo aquí; un asesor te puede confirmar. ¿Te gustaría agendar una visita?")
    # Pregunta por habitaciones
    elif "habitacion" in t or "habitaciones" in t or "alcoba" in t or "cuartos" in t:
        hab = prop.get("habitaciones")
        if hab is not None:
            lines.append(f"Tiene {hab} habitación(es).")
        else:
            lines.append("Un asesor te puede dar ese detalle. ¿Agendamos una visita?")
    else:
        # Resumen breve: habitaciones, baños, precio
        partes = []
        if prop.get("habitaciones") is not None:
            partes.append(f"{prop['habitaciones']} hab")
        if prop.get("banos") is not None:
            partes.append(f"{prop['banos']} baño(s)")
        if prop.get("precio"):
            partes.append(_format_precio(float(prop["precio"])))
        if partes:
            lines.append(f"Esa tiene: {', '.join(partes)}.")
        else:
            lines.append("¿Quieres que agendemos una visita para que un asesor te cuente todos los detalles?")
    agenda_msg = _cfg("mensaje_agendar_cita", "¿Te gustaría agendar una visita?")
    lines.append(agenda_msg)
    return {"text": " ".join(lines), "actions": [], "context": contexto}


def handle_pedir_otra_opcion(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    """
    "Qué otra tienes disponible": misma búsqueda pero excluyendo la(s) ya mostrada(s).
    Responde de forma fluida: "Claro, también tengo [Casa X]. Tiene N hab, M baños..."
    """
    tipo = contexto.get("tipo")
    precio_min = contexto.get("presupuesto_min")
    precio_max = contexto.get("presupuesto_max")
    habitaciones = contexto.get("habitaciones")
    ubicacion = (contexto.get("ubicacion") or "").strip() or None
    mostradas = contexto.get("propiedades_mostradas_ids") or []
    ref_id = contexto.get("referencia_id")
    if ref_id and ref_id not in mostradas:
        mostradas = mostradas + [ref_id]
    exclude_ids = mostradas if mostradas else ([ref_id] if ref_id else None)

    props = buscar_propiedades(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max,
        habitaciones=habitaciones,
        ubicacion=ubicacion,
        exclude_ids=exclude_ids,
        limite=4,
    )
    if not props:
        # No hay más con esos filtros; ofrecer búsqueda más amplia o visita
        msg = "Con esos criterios ya te mostré las que tenía. ¿Quieres que ajustemos (más habitaciones, otra zona) o agendamos una visita y un asesor te muestra más opciones?"
        return {"text": msg, "actions": [], "context": contexto}

    primera = props[0]
    card = _card_propiedad(primera, base_url)
    titulo = primera.get("titulo") or "esta opción"
    hab = primera.get("habitaciones")
    banos = primera.get("banos")
    prec = _format_precio(float(primera["precio"])) if primera.get("precio") else ""
    partes = [f"Claro, también tengo **{titulo}**."]
    if hab is not None:
        partes.append(f"Tiene {hab} habitación(es).")
    if banos is not None:
        partes.append(f"{banos} baño(s).")
    if prec:
        partes.append(f"Precio {prec}.")
    partes.append("¿Te interesa o prefieres que te muestre otra? También puedo agendar una visita.")
    agenda_msg = _cfg("mensaje_agendar_cita", "¿Te gustaría agendar una visita?")
    partes.append(agenda_msg)

    ctx = dict(contexto)
    ctx["tipo_referencia"] = "propiedad"
    ctx["referencia_id"] = primera["id"]
    nuevas_mostradas = list(mostradas) + [primera["id"]]
    ctx["propiedades_mostradas_ids"] = nuevas_mostradas[:10]

    return {"text": " ".join(partes), "actions": [], "cards": [card], "context": ctx}


def handle_pedir_recomendacion(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    """Recomendaciones: usa motor de razonamiento con filtros relajados (destacados)."""
    tipo = contexto.get("tipo")
    ubicacion = (contexto.get("ubicacion") or "").strip() or None
    match_type, props, proyectos, reasoning_text = run_reasoning(
        tipo=tipo,
        precio_min=None,
        precio_max=None,
        habitaciones=None,
        ubicacion=ubicacion,
        pide_proyectos=False,
    )
    agenda_msg = _cfg("mensaje_agendar_cita", "¿Quieres agendar una visita? Te pido nombre, correo y teléfono para confirmar.")
    cards: List[Dict[str, Any]] = []
    for p in props[:4]:
        cards.append(_card_propiedad(p, base_url))
    for pr in proyectos[:3]:
        cards.append(_card_proyecto(pr, base_url))
    lines = [reasoning_text]
    if cards:
        lines.append(agenda_msg)
    return {"text": "\n\n".join(lines), "actions": [], "cards": cards, "context": contexto}


def handle_comparar_opciones(
    texto: str,
    contexto: Dict[str, Any],
    conversacion_id: Optional[str],
    base_url: str,
) -> Dict[str, Any]:
    """Comparar opciones: mismo flujo que recomendación; motor razona con datos reales."""
    return handle_pedir_recomendacion(texto, contexto, conversacion_id, base_url)


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
        INTENT_PREGUNTA_SOBRE_PROPIEDAD: lambda: handle_pregunta_sobre_propiedad(texto, contexto, conversacion_id, base_url),
        INTENT_PEDIR_OTRA_OPCION: lambda: handle_pedir_otra_opcion(texto, contexto, conversacion_id, base_url),
        INTENT_COMPARAR_OPCIONES: lambda: handle_comparar_opciones(texto, contexto, conversacion_id, base_url),
        INTENT_PEDIR_RECOMENDACION: lambda: handle_pedir_recomendacion(texto, contexto, conversacion_id, base_url),
        INTENT_PEDIR_INFORMACION: lambda: handle_pedir_informacion(texto, conversacion_id, base_url),
        INTENT_AGENDAR_CITA: lambda: handle_agendar_cita(texto, contexto, conversacion_id, base_url),
        INTENT_CONFIRMAR_DATOS: lambda: handle_confirmar_datos(texto, contexto, conversacion_id, base_url),
        INTENT_DUDA_GENERAL: lambda: handle_duda_general(texto, conversacion_id, base_url),
    }
    h = handlers.get(intent, lambda: handle_duda_general(texto, conversacion_id, base_url))
    out = h()
    if "context" not in out:
        out["context"] = {}

    # Célula inteligente (Gemini): genera la respuesta desde datos de la BD; si falla, se usa el borrador
    if llm_generate_reply and out.get("text"):
        try:
            data_ctx = build_data_context(out.get("cards")) if build_data_context else None
            if not (data_ctx or "").strip():
                data_ctx = f"Contexto: {out['text'][:500]}"
            last_user = (contexto.get("last_user_message") or "").strip() or None
            last_bot = (contexto.get("last_bot_message") or "").strip() or None
            system_prompt = _cfg("prompt_sistema") or _cfg("instrucciones_ia") or None
            natural = llm_generate_reply(
                texto,
                out["text"],
                intent=intent,
                data_context=data_ctx,
                last_user_message=last_user,
                last_bot_message=last_bot,
                system_prompt=system_prompt,
            )
            if natural:
                out["text"] = natural
                out["llm_used"] = True
        except Exception:
            pass

    out["intent"] = intent
    return out
