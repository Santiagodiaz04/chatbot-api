# reasoning.py - Motor de razonamiento del chatbot inmobiliario
"""
Flujo: ENTENDER → CONSULTAR → RAZONAR → PERSUADIR.

- Consulta la base de datos real (nunca inventa).
- Si hay coincidencia exacta → la muestra.
- Si NO hay coincidencia exacta → explica la situación, ofrece la mejor alternativa
  y resalta beneficios reales (orientado a conversión).
"""

from typing import Any, Dict, List, Optional, Tuple

from db import buscar_propiedades, buscar_proyectos


# --- Tipos de resultado del razonamiento ---
MATCH_EXACT = "exact"
MATCH_ALTERNATIVES = "alternatives"
MATCH_NONE = "none"


def _format_precio(v: Optional[float]) -> str:
    if v is None:
        return ""
    if v >= 1_000_000:
        return f"${v/1_000_000:.1f}M" if v % 1_000_000 == 0 else f"${v/1_000_000:.2f}M"
    return f"${v:,.0f}"


def _beneficios_cortos(prop: Dict[str, Any]) -> List[str]:
    """Extrae o infiere beneficios breves para persuadir (sin inventar)."""
    beneficios = []
    hab = prop.get("habitaciones")
    if hab is not None:
        beneficios.append(f"{hab} habitaciones")
    area = prop.get("area_construida") or prop.get("area_total")
    if area and float(area) > 80:
        beneficios.append("muy amplia")
    if prop.get("ubicacion"):
        beneficios.append("bien ubicada")
    desc = (prop.get("descripcion") or "").lower()
    if "iluminad" in desc or "luz" in desc:
        beneficios.append("bien iluminada")
    if "parqueadero" in desc or "garaje" in desc:
        beneficios.append("con parqueadero")
    if not beneficios:
        beneficios.append("disponible para visita")
    return beneficios[:3]


def run_reasoning(
    tipo: Optional[str] = None,
    precio_min: Optional[float] = None,
    precio_max: Optional[float] = None,
    habitaciones: Optional[int] = None,
    ubicacion: Optional[str] = None,
    pide_proyectos: bool = False,
) -> Tuple[str, List[Dict], List[Dict], str]:
    """
    Motor de razonamiento: consulta BD, razona y genera texto persuasivo.

    Returns:
        (match_type, properties, projects, reasoning_text)
        - match_type: "exact" | "alternatives" | "none"
        - reasoning_text: párrafo en español para el bot (nunca "no hay" sin alternativa)
    """
    ubic = ubicacion.strip() if ubicacion else None
    # Buscar por nombre de proyecto/propiedad o ubicación: mismo término en titulo y ubicacion
    titulo_term = ubic  # así "busco Ibiza" encuentra por nombre (titulo) y por ubicación

    # --- 1. CONSULTAR: coincidencia exacta ---
    props_exact = buscar_propiedades(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max,
        habitaciones=habitaciones,
        ubicacion=ubic,
        titulo=titulo_term,
        limite=6,
    )
    proyectos_exact = buscar_proyectos(ubicacion=ubic, limite=6 if pide_proyectos else 3)
    if precio_max is not None and proyectos_exact:
        proyectos_exact = [p for p in proyectos_exact if (p.get("precio_desde") or 0) <= precio_max]

    if props_exact:
        # Coincidencia exacta: mensaje cercano y humano ("Sí, claro. Tengo...")
        count = len(props_exact)
        reasoning = f"Sí, claro. Tengo {count} opción(es) que coinciden con lo que buscas. ¿Te gustaría ver más detalles o agendar una visita para conocerlas? 🏡"
        return MATCH_EXACT, props_exact, [], reasoning

    if proyectos_exact and (pide_proyectos or not tipo):
        count = len(proyectos_exact)
        reasoning = f"En proyectos encontré {count} opción(es) que encajan. ¿Quieres que te cuente más o agendamos una visita? 📅"
        return MATCH_EXACT, [], proyectos_exact, reasoning

    # --- 2. RAZONAR: no hay exacto → buscar mejor alternativa ---
    hab_relajado = (habitaciones - 1) if habitaciones and habitaciones > 1 else None
    precio_max_relajado = (precio_max * 1.2) if precio_max else None

    props_alt = buscar_propiedades(
        tipo=tipo,
        precio_min=precio_min,
        precio_max=precio_max_relajado,
        habitaciones=hab_relajado,
        ubicacion=ubic,
        titulo=titulo_term,
        limite=6,
    )

    if props_alt:
        # Hay alternativas: explicar situación y resaltar beneficios reales
        primera = props_alt[0]
        beneficios = _beneficios_cortos(primera)
        beneficio_texto = ", ".join(beneficios)
        hab_alt = primera.get("habitaciones")
        prec_alt = _format_precio(float(primera["precio"])) if primera.get("precio") else ""

        if habitaciones and not hab_relajado:
            # Pedía N hab y no hay; alternativa tiene menos
            reasoning = (
                f"En este momento no tengo disponibles casas de {habitaciones} habitaciones, "
                f"pero sí una opción de {hab_alt or '2'} habitaciones que es {beneficio_texto}. "
                f"Precio {prec_alt}. ¿Te gustaría que te la muestre o agendamos una visita para verla? 🏡✨"
            )
        elif habitaciones:
            reasoning = (
                f"No encontré exactamente {habitaciones} habitaciones, "
                f"pero tengo opciones de {hab_alt or '2'} hab que son {beneficio_texto}. "
                f"Por ejemplo desde {prec_alt}. ¿Te las muestro o agendamos una visita? 📅"
            )
        elif precio_max:
            reasoning = (
                f"Dentro de ese presupuesto no hay coincidencia exacta, "
                f"pero sí opciones un poco más altas que son {beneficio_texto}. "
                f"¿Te gustaría verlas o ajustamos el rango? Siempre podemos agendar una visita. 🏡"
            )
        else:
            reasoning = (
                f"No encontré algo exacto con esos criterios, "
                f"pero sí opciones cercanas: {beneficio_texto}. "
                f"¿Te las muestro o agendamos una visita para que un asesor te ayude? 🙂"
            )
        return MATCH_ALTERNATIVES, props_alt, [], reasoning

    # --- 3. Sin alternativas cercanas: búsqueda muy amplia ---
    props_general = buscar_propiedades(tipo=tipo, ubicacion=ubic, limite=4)
    proyectos_general = buscar_proyectos(ubicacion=ubic, limite=3)

    if props_general or proyectos_general:
        reasoning = (
            "Por ahora no tengo justo lo que buscas con esos criterios, "
            "pero sí otras opciones que podrían interesarte. "
            "¿Quieres que te las muestre o prefieres que agendemos una visita y un asesor te ayude a encontrar lo ideal? 📅"
        )
        return MATCH_ALTERNATIVES, props_general, proyectos_general, reasoning

    # --- 4. Nada en BD: mensaje honesto pero orientado a acción ---
    if precio_max:
        reasoning = (
            "En este momento no tengo propiedades dentro de ese presupuesto. "
            "¿Te gustaría que te muestre opciones un poco más altas o que agendemos una visita para que un asesor te comente alternativas? 🙂"
        )
    else:
        reasoning = (
            "Por ahora no tengo propiedades con esas características. "
            "¿Quieres que ajustemos criterios (habitaciones, zona, tipo) o agendamos una visita y te ayudamos a encontrar algo? 📅"
        )
    return MATCH_NONE, [], [], reasoning
