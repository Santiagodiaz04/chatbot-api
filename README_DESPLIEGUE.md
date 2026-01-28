# 🚀 Guía Rápida de Despliegue - Chatbot API

## Opción 1: Railway (Recomendado - Gratis)

### Pasos:

1. **Crear cuenta en Railway.app** (con GitHub)

2. **Subir código a GitHub**:
   ```bash
   cd chatbot-api
   git init
   git add .
   git commit -m "Chatbot API"
   # Crear repo en GitHub y hacer push
   ```

3. **En Railway**:
   - Click "New Project" → "Deploy from GitHub"
   - Selecciona tu repositorio
   - Railway detectará Python automáticamente

4. **Configurar Variables de Entorno** (Settings → Variables):
   ```
   DB_HOST=localhost
   DB_NAME=u879179603_webctr
   DB_USER=u879179603_admi
   DB_PASS=K@p4CrgFFg4
   PHP_BASE_URL=https://ctrbienesraices.com
   CORS_ORIGINS=https://ctrbienesraices.com,https://www.ctrbienesraices.com
   ```

5. **Obtener URL**: Railway te dará una URL como `https://tu-proyecto.up.railway.app`

6. **Configurar en Hostinger** (`config/config.php` línea ~125):
   ```php
   $chatbot_url = 'https://tu-proyecto.up.railway.app';
   ```

---

## Opción 2: Render (Gratis)

1. **Crear cuenta en render.com**

2. **New → Web Service** → Conectar GitHub

3. **Configurar**:
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `uvicorn main:app --host 0.0.0.0 --port $PORT`
   - **Environment Variables**: Igual que Railway

4. **Obtener URL** y configurar en `config/config.php`

**Nota**: Render puede "dormir" después de inactividad (tarda ~30 seg en despertar)

---

## Opción 3: VPS (Hostinger VPS o DigitalOcean)

Ver `GUIA_HOSTINGER.md` para instrucciones completas.

---

## Verificar que Funciona

1. Abre `https://tu-api.railway.app/health` en el navegador
2. Debe responder: `{"status":"ok","service":"chatbot-api"}`
3. Si funciona, configura la URL en `config/config.php`
4. Prueba el chatbot en tu sitio web

---

## Troubleshooting

- **Error 502**: La API no está corriendo, revisa logs en Railway/Render
- **Error CORS**: Agrega tu dominio a `CORS_ORIGINS`
- **Error de BD**: Verifica credenciales de MySQL en variables de entorno
