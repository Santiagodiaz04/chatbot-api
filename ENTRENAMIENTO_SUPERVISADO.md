# Sistema de entrenamiento supervisado del chatbot

## Resumen

El panel admin incluye un **entorno de entrenamiento supervisado** donde los administradores actúan como “entrenadores humanos”: simulan conversaciones, evalúan respuestas y corrigen el texto. Solo las respuestas marcadas como **Correcta** o **Corregida** se usan para mejorar el comportamiento del chatbot en producción.

## Comportamiento idéntico al usuario final

- El chat del panel admin llama a la **misma API** (`POST /chat`) que el chat público.
- Se envía `contexto.origen = "admin"` para que el backend guarde cada turno en `chatbot_entrenamiento` y devuelva `entrenamiento_id`.
- **No existe modo demo**: la lógica (NLU, handlers, reasoning, LLM) es la misma que para el usuario final.

## Flujo de entrenamiento

1. **Simulación**: El admin escribe como un cliente (ej: “Quiero una casa de 4 habitaciones”).
2. **Respuesta**: El chatbot responde con la lógica real (misma que en la web).
3. **Registro**: Cada turno se guarda en `chatbot_entrenamiento` con estado `pendiente`.
4. **Evaluación**: El admin puede marcar:
   - **✔ Correcta**: la respuesta se usará como ejemplo para preguntas similares.
   - **❌ Incorrecta**: no se reutiliza; opcionalmente se puede añadir una “respuesta corregida” (entonces se guarda como `corregida` y sí se usa).
   - **⚠ Mejorable**: igual que Incorrecta; se puede corregir o solo marcar.
5. **Aprendizaje**: En cada respuesta, el backend consulta `entrenamiento_match(texto, intencion)`. Si existe un ejemplo aprobado (`correcta` o `corregida`) con input e intención similares, se usa esa respuesta (corregida o original) en lugar del texto generado por el handler.

## Reglas de aprendizaje

- **Solo** registros con `estado_aprobacion IN ('correcta', 'corregida')` se usan para mejorar respuestas.
- Las marcadas como **Incorrectas** (sin corrección) no se reutilizan.
- El aprendizaje es **incremental y controlado**: el bot no cambia sin aprobación humana.

## Estructura de datos (`chatbot_entrenamiento`)

| Campo               | Uso                                      |
|---------------------|------------------------------------------|
| input_usuario       | Pregunta del usuario                     |
| respuesta_chatbot   | Respuesta generada por el bot            |
| respuesta_corregida | Texto corregido por el admin (opcional)  |
| intencion           | Intención detectada (NLU)                 |
| contexto_json       | Filtros/contexto del turno               |
| estado_aprobacion   | pendiente \| correcta \| incorrecta \| mejorable \| corregida |
| fecha_creacion      | Momento del turno                        |

## API

- **POST /chat**  
  Con `contexto.origen = "admin"`: además de responder, guarda el turno en `chatbot_entrenamiento` y devuelve `entrenamiento_id` en la respuesta.

- **POST /entrenamiento/evaluar**  
  Body: `{ "entrenamiento_id": int, "estado_aprobacion": "correcta"|"incorrecta"|"mejorable"|"corregida", "respuesta_corregida": string opcional }`  
  Actualiza la evaluación del turno.

- **GET /entrenamiento**  
  Query: `limite`, `estado`, `intencion` (opcionales).  
  Devuelve la lista de registros para el panel admin.

## Migración

Ejecutar en la base de datos:

```bash
mysql -u usuario -p ctr_bienes_raices < database/migration_chatbot_entrenamiento.sql
```

O desde phpMyAdmin / cliente MySQL: ejecutar el contenido de `database/migration_chatbot_entrenamiento.sql`.

## Panel admin (PHP)

- **Chat de entrenamiento**: misma interfaz que el chat; bajo cada respuesta del bot aparecen botones “Correcta”, “Incorrecta”, “Mejorable” y, si aplica, campo para “Guardar corrección”.
- **Registros de entrenamiento**: tabla con turnos guardados, filtros por estado y límite; solo informativa (la evaluación se hace desde el chat).

## Ejemplo de uso

1. Admin escribe: “Quiero una casa de 4 habitaciones”.
2. Bot responde: “No tengo casas disponibles”.
3. Admin marca **Incorrecta** y escribe la corrección: “Actualmente no tengo casas de 4 habitaciones, pero sí opciones de 3 muy amplias y bien ubicadas. ¿Te gustaría conocerlas o agendar una visita?”
4. Admin pulsa “Guardar corrección”. Se guarda como `corregida` con esa respuesta.
5. En siguientes conversaciones (admin o usuario final), si la pregunta e intención son similares, el bot usará la respuesta aprobada/corregida en lugar de la generada por defecto.
