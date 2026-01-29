# Célula inteligente (IA) del chatbot

La **célula inteligente** es el módulo que usa Gemini para procesar las respuestas del bot con:

1. **Análisis del texto** – El mensaje del usuario se envía a la IA junto con el borrador.
2. **Contexto de datos** – Se envía un resumen de lo que devolvió la BD (propiedades/proyectos) para que la respuesta sea coherente con los datos reales.
3. **Conversación fluida** – Se envía el último intercambio (mensaje anterior del usuario y respuesta anterior del bot) para mantener continuidad.

## Flujo

1. El backend detecta intención, consulta BD y genera un **borrador** de respuesta (texto + cards).
2. Se construye **data_context** a partir de las cards (títulos, precios, habitaciones, ubicación).
3. El frontend envía en **contexto** (si existe): `last_user_message`, `last_bot_message`.
4. La célula (Gemini) recibe: mensaje actual, borrador, data_context, último intercambio.
5. Gemini devuelve una respuesta **natural y conversacional** sin inventar datos.

## Archivos

- **llm_client.py**: `build_data_context(cards)`, `process_response(...)`, `generate_reply(...)`.
- **handlers.py**: En `dispatch()`, se llama a la célula con data_context (de las cards) y last_user_message / last_bot_message (del contexto).
- **chatbot.js**: Envía `last_user_message` y `last_bot_message` en `contexto` en cada petición; los actualiza tras cada respuesta.

## Variables

- `LLM_ENABLED=1` y `GEMINI_API_KEY` en Railway (o `.env`) para activar la célula.
- Sin IA, se usa siempre el borrador del backend (sin cambios).

## Límites

- Gemini no consulta la BD; solo recibe el resumen que construye el backend.
- No se inventan precios ni propiedades; la IA reescribe usando solo la información proporcionada.
