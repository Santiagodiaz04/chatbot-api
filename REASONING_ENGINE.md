# Motor de razonamiento del chatbot

El chatbot se comporta como una **secretaria experta** inmobiliaria: entiende, consulta la BD, razona y persuade. **Nunca inventa datos**; siempre se alimenta de la base de datos.

---

## Flujo obligatorio: ENTENDER → CONSULTAR → RAZONAR → PERSUADIR

### 1. ENTENDER
- Qué quiere el cliente (intención: buscar, comparar, recomendar, agendar, etc.).
- Qué es obligatorio (ej.: habitaciones) y qué es flexible (presupuesto, ubicación).
- Implementación: `nlu.py` (detección de intención y entidades) + contexto de conversación.

### 2. CONSULTAR
- Consulta la **base de datos real** (propiedades, proyectos).
- Búsqueda con coincidencia exacta según filtros (tipo, habitaciones, presupuesto, ubicación).
- Implementación: `db.buscar_propiedades`, `db.buscar_proyectos`; orquestado en `reasoning.run_reasoning`.

### 3. RAZONAR
- **Si hay coincidencias exactas** → mostrarlas y invitar a ver o agendar.
- **Si NO hay coincidencias exactas**:
  - Explicar la situación de forma natural.
  - Ofrecer la **mejor alternativa disponible** (filtros relajados: 1 hab menos, hasta +20% presupuesto).
  - Resaltar **beneficios reales** (amplia, bien ubicada, bien iluminada, etc.) a partir de datos de la BD.
- Implementación: `reasoning.py` (`run_reasoning`).

### 4. PERSUADIR
- Mostrar valor y crear confianza.
- Reducir fricción e **invitar siempre a agendar cita**.
- Tono: amable, cercano, profesional; emojis moderados 🙂🏡📅.
- Implementación: textos generados en `reasoning.py` + célula IA (`llm_client.py`) con personalidad por defecto.

---

## Ejemplo de razonamiento esperado

**Usuario:** “Busco una casa de 3 habitaciones”

**Base de datos:** Solo hay casas de 2 habitaciones.

**Respuesta esperada (motor de razonamiento):**
> En este momento no tengo disponibles casas de 3 habitaciones, pero sí una opción de 2 habitaciones que es muy amplia, bien iluminada y con posibilidad de adecuación. Precio $X. ¿Te gustaría que te la muestre o agendamos una visita para verla? 🏡✨

El texto se genera en `reasoning.run_reasoning` (beneficios desde `_beneficios_cortos`) y la IA lo puede suavizar sin inventar datos.

---

## Archivos del motor

| Archivo | Responsabilidad |
|--------|------------------|
| **reasoning.py** | Consulta BD (exacta + relajada), construye texto de razonamiento y beneficios. |
| **nlu.py** | Detección de intención y entidades (habitaciones, tipo, presupuesto, ubicación). |
| **handlers.py** | Orquesta: entidades → `run_reasoning` → cards + texto → célula IA. |
| **llm_client.py** | Célula IA: personalidad por defecto (secretaria), refuerza valor e invitación a agendar. |
| **db.py** | Acceso a BD (propiedades, proyectos). |

---

## Intenciones soportadas

- `buscar_propiedad` – Búsqueda con filtros; motor aplica exacto → alternativas → persuasión.
- `comparar_opciones` – Comparar; usa mismo motor con filtros relajados (recomendaciones).
- `pedir_recomendacion` – “Qué me recomiendas”; motor con filtros desde contexto.
- `pedir_informacion` – FAQs, ubicación, quiénes somos, información por lugar (ej. Ibiza).
- `agendar_cita` – Flujo nombre → correo → teléfono → fecha → hora.
- `duda_general` – Fallback; intenta FAQs y respuestas genéricas.

---

## Reglas de oro

- **NUNCA** inventar datos.
- **NUNCA** prometer lo que no existe en BD.
- **SIEMPRE** consultar la base de datos.
- **SIEMPRE** ofrecer una alternativa si no hay coincidencia exacta.
- **SIEMPRE** orientar al cierre (ver propiedad o agendar cita).

---

## Ajustes desde el admin

- **chatbot_config**: claves `prompt_sistema` o `instrucciones_ia` para instrucciones extra a la IA.
- Las respuestas del motor (textos de `reasoning.py`) se pueden afinar editando ese módulo; la IA solo humaniza y refuerza sin inventar.
