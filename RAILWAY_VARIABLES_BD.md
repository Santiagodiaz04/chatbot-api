# Variables de BD en Railway (conectar a MySQL de Hostinger)

El error `Can't connect to MySQL server on 'localhost:3306'` significa que en Railway **no están configuradas** (o están por defecto) las variables de base de datos. Railway intenta conectar a `localhost` en su propio servidor; la BD está en **Hostinger**.

---

## 1. En Hostinger: habilitar MySQL remoto

1. Entra a **hPanel** (Hostinger) → **Bases de datos** → **MySQL**.
2. Busca **Remote MySQL** / **MySQL remoto** o **Acceso remoto**.
3. Actívalo y añade las **IPs permitidas**:
   - Si Hostinger permite “cualquier host”, usa `%` o `0.0.0.0/0`.
   - Si pide IP concreta, Railway no tiene IP fija; en ese caso prueba primero con `%` (todos) para comprobar, y luego puedes restringir si Hostinger te da las IPs de Railway.
4. Anota el **host de MySQL para acceso remoto** (no uses `localhost`). Suele ser algo como:
   - `srv123.hostinger.com`, o
   - El que aparezca en la sección “Remote MySQL” / “Conexión remota”.
   - Si solo ves “localhost”, en muchos planes el host remoto es el **mismo nombre del servidor** que aparece en el panel (ej. tipo `srv123.hostinger.com`).

---

## 2. En Railway: variables de entorno

En **Railway** → tu proyecto → **Variables** (o **Settings → Variables**), define estas variables con los valores de **producción de Hostinger** (los mismos que usa tu PHP en ctrbienesraices.com):

| Variable   | Valor (ejemplo)        | Descripción |
|-----------|------------------------|-------------|
| `DB_HOST` | **Host remoto MySQL** (ej. `srv123.hostinger.com`) | **No** uses `localhost`. El que te dé Hostinger para conexión remota. |
| `DB_PORT` | `3306`                 | Puerto MySQL (normalmente 3306). |
| `DB_NAME` | `u879179603_webctr`    | Nombre de la BD (el de producción en Hostinger). |
| `DB_USER` | `u879179603_admi`      | Usuario MySQL de Hostinger. |
| `DB_PASS` | *(la contraseña de esa BD en Hostinger)* | La misma que en `config/database.php` en producción. |

- Si no pones `DB_HOST`, la API usa `localhost` y seguirá el error actual.
- Después de guardar las variables, Railway suele hacer **redeploy** automático. Si no, inicia un deploy manual.

---

## 3. Comprobar

1. Espera a que el deploy termine.
2. Abre: `https://web-production-8bc86.up.railway.app/health/db`
3. Si todo va bien verás: `{"status":"ok","db":"connected"}`.
4. Si sigue fallando, la respuesta incluirá el mensaje de error (host, usuario, etc.). Revisa:
   - Que **Remote MySQL** esté activado en Hostinger y las IPs permitidas.
   - Que `DB_HOST` sea el **host remoto** (no `localhost`).
   - Que usuario, contraseña y nombre de BD coincidan con los de Hostinger.

---

## Sobre los errores en consola

- **503** en `/health/db`: es la respuesta de la API cuando la BD está desconectada. Al configurar bien las variables y MySQL remoto, debería pasar a 200.
- **404**: suele ser otro recurso (p. ej. favicon, o una ruta que el frontend pide y no existe). No está causado por `/health/db`.

---

## IA generativa (opcional, gratis)

Para que el bot responda con lenguaje más natural (IA), en Railway añade:

| Variable | Valor | Descripción |
|----------|--------|-------------|
| `LLM_ENABLED` | `1` | Activa humanizar respuestas con Gemini. |
| `GEMINI_API_KEY` | Tu API key | Gratis en [Google AI Studio](https://aistudio.google.com/apikey). |

Sin estas variables el chatbot sigue igual (respuestas predeterminadas). Con ellas, el texto se reescribe con IA; las cards, citas y BD no cambian.
