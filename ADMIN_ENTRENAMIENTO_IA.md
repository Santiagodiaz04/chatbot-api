# Entrenar / configurar la IA desde el panel Admin

La IA del chatbot **no se entrena** en el panel de Gemini; se configura desde tu **panel Admin** mediante textos que el bot usa para responder. El “alimento” de datos viene de tu **base de datos** (propiedades, proyectos).

---

## 1. Prompt de sistema (instrucciones para la IA)

En el **panel Admin** → **Chatbot** → **Mensajes / Configuración** (tabla `chatbot_config`), puedes añadir una de estas claves para “entrenar” cómo debe responder la IA:

| Clave | Uso |
|-------|-----|
| `prompt_sistema` | Instrucciones principales que se envían a la IA (Gemini). |
| `instrucciones_ia` | Alternativa a `prompt_sistema`. |

**Ejemplo de valor** (lo que puedes pegar en el valor de esa clave):

```
Responde siempre en tono cercano y profesional. Si el usuario pide casas en renta, habla solo de opciones en renta. Si pide agendar, confirma día y hora antes de pedir nombre. Cuando muestres propiedades, menciona precio y ubicación de forma natural. No inventes datos; usa solo la información que te pasamos desde la base de datos.
```

- Ese texto se envía a la IA en cada respuesta.
- La IA sigue esas instrucciones además de las que ya lleva el sistema (mismo idioma, no inventar precios, etc.).
- **No hace falta entrenar en Gemini**; con este texto ya estás “entrenando” el estilo y reglas de respuesta.

---

## 2. De dónde salen los datos (BD)

- **Propiedades**: tabla `propiedades` (venta, renta, lotes).
- **Proyectos**: tabla `proyectos`.
- **FAQs**: tabla `chatbot_faqs` (preguntas y respuestas).
- **Config**: tabla `chatbot_config` (saludo, despedida, `prompt_sistema`, `respuesta_ubicacion`, `respuesta_quienes_somos`, etc.).

La IA **no consulta la BD directamente**; el backend consulta la BD, prepara un resumen (propiedades/proyectos encontrados) y ese resumen se envía a la IA para que redacte la respuesta. Así la IA solo “habla” con datos reales.

---

## 3. Comportamiento inteligente ya implementado

- **“Mañana cita a las 8 am”**: detecta día (mañana) y hora (8:00) y los guarda para la cita.
- **“Casas en renta”**: solo se buscan y muestran propiedades de tipo **renta** en la BD.
- **“Información de Ibiza”** (o “info de [lugar]”): se buscan propiedades y proyectos en ese lugar y se muestran con imágenes.
- **Sí / No**: se detecta confirmación (sí, claro, no, cancelar) para flujos de cita.
- **Horarios**: si están agendando, se muestran horarios disponibles y se puede decir “¿Quieres agendar en uno de estos horarios?”.

Todo esto lo hace el backend con la BD; la IA se encarga de redactar la respuesta de forma natural usando esos datos y el `prompt_sistema` que pongas en el admin.

---

## 4. Cómo añadir `prompt_sistema` en el Admin

1. Entra al **panel Admin** del sitio.
2. Ve a la sección del **Chatbot** (mensajes / configuración).
3. Si existe un formulario para editar claves/valores de configuración:
   - Añade una clave **`prompt_sistema`** (o **`instrucciones_ia`**).
   - En el valor pega las instrucciones que quieras para la IA (ejemplo de la tabla de arriba).
4. Si la config se guarda en la tabla `chatbot_config`:
   - Inserta o actualiza una fila con `key = 'prompt_sistema'` y `value = 'Tu texto aquí'`.

Después de guardar, las siguientes respuestas del chat ya usarán ese “entrenamiento” (instrucciones) sin tener que configurar nada en el panel de Gemini.
