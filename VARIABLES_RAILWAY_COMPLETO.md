# Variables de entorno – Railway (producción)

Referencia de **todas** las variables que usa la API del chatbot: conexión a BD e integración con IA.

---

## Resumen rápido

| Variable        | ¿La tienes? (según tu pantalla) | Uso                          |
|----------------|----------------------------------|------------------------------|
| `CORS_ORIGINS` | Sí                               | Dominios permitidos (front)  |
| `DB_HOST`      | Sí                               | Host MySQL (remoto Hostinger)|
| `DB_NAME`      | Sí                               | Nombre de la BD              |
| `DB_USER`      | Sí                               | Usuario MySQL                |
| `DB_PASS`      | Sí                               | Contraseña MySQL              |
| `PHP_BASE_URL` | Sí                               | URL base del sitio PHP       |
| `DB_PORT`      | Opcional                         | Puerto MySQL (default 3306)  |
| `PORT`         | Railway lo define                | Puerto de la API              |
| **`LLM_ENABLED`**  | **Añadir**                    | Activar IA (1 = sí)           |
| **`GEMINI_API_KEY`** | **Añadir**                 | Clave API de Google Gemini   |

---

## 1. Conexión a la base de datos

La API usa la **misma base de datos** que tu sitio PHP en Hostinger. En Railway debes usar el **host de MySQL remoto** (no `localhost`).

| Variable   | Dónde sale el valor | Descripción |
|-----------|---------------------|-------------|
| `DB_HOST` | Hostinger → Remote MySQL | Host remoto (ej. `srv893.hstgr.io`). **No** uses `localhost`. |
| `DB_PORT` | Opcional | Si no la pones, se usa `3306`. |
| `DB_NAME` | Hostinger / PHP producción | Ej. `u879179603_webctr` (el mismo que en `config/database.php` en producción). |
| `DB_USER` | Hostinger / PHP producción | Ej. `u879179603_admi`. |
| `DB_PASS` | Hostinger / PHP producción | La misma contraseña que en `config/database.php` en producción. |

- Si en Railway pones `DB_HOST=localhost`, la API intentará conectar a MySQL dentro de Railway y fallará. Debe ser el host remoto de Hostinger.
- En Hostinger hay que tener **MySQL remoto** activado y permitir conexiones (por ejemplo desde cualquier host si no te dan IP fija).

---

## 2. Sitio PHP y CORS

| Variable        | Descripción |
|----------------|-------------|
| `PHP_BASE_URL` | URL base del sitio (ej. `https://ctrbienesraices.com`). Sin barra final. Se usa para enlaces de propiedades y llamadas a `procesar-cita.php`, etc. |
| `CORS_ORIGINS` | Orígenes permitidos para el navegador, separados por coma. Ej. `https://ctrbienesraices.com,https://www.ctrbienesraices.com`. |

---

## 3. IA generativa (Gemini)

Para que el bot **humanice** las respuestas con IA (Gemini, plan gratuito):

1. En Railway → **Variables** → **Add**:
   - **Variable:** `LLM_ENABLED`  
     **Valor:** `1`
2. Otra variable:
   - **Variable:** `GEMINI_API_KEY`  
     **Valor:** pega aquí tu clave de API de Gemini (la que obtuviste en Google AI Studio).

- Sin `LLM_ENABLED=1` o sin `GEMINI_API_KEY`, el chatbot sigue funcionando con respuestas predeterminadas (sin IA).
- **No subas la API key a GitHub ni la pongas en el código.** Solo en variables de entorno (Railway o `.env` local).

Después de añadir o cambiar variables, Railway suele hacer **redeploy** automático. Si no, lanza un deploy manual.

---

## 4. Comprobar que todo va bien

1. **BD:** `https://tu-app.up.railway.app/health/db`  
   Debe devolver `{"status":"ok","db":"connected"}`.
2. **Servicio:** `https://tu-app.up.railway.app/health`  
   Debe devolver `{"status":"ok","service":"chatbot-api"}`.
3. **IA (Gemini):** Abre en el navegador:
   ```
   https://tu-app.up.railway.app/health/llm
   ```
   - Si la IA está activa verás: `"llm_enabled": true`, `"gemini_configured": true`, `"message": "IA (Gemini) activa"`.
   - Si no: `"llm_enabled": false` o `"gemini_configured": false`.
   - En cada respuesta del chat (DevTools → Network → respuesta de `/chat`) el campo `llm_used: true` indica que esa respuesta fue humanizada por Gemini.

---

## 5. Origen de cada variable en el código

- `config.py`: lee `DB_HOST`, `DB_PORT`, `DB_NAME`, `DB_USER`, `DB_PASS`, `PHP_BASE_URL`, `CORS_ORIGINS`, `LLM_ENABLED`, `GEMINI_API_KEY`.
- `db.py`: usa `DB_*` y `DB_CHARSET` (fijo) para conectar a MySQL.
- `main.py`: usa `PORT` (Railway lo inyecta) y CORS.
- `llm_client.py`: usa `GEMINI_API_KEY` y `LLM_ENABLED` para llamar a Gemini.

Si alguna variable no está definida en Railway, la API usa los valores por defecto de `config.py` (p. ej. `localhost` para BD), por eso es importante tener **todas** las de producción configuradas en Railway.
