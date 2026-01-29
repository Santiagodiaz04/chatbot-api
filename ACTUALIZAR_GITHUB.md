# Cómo actualizar el proyecto en GitHub (sin romper Railway)

Railway está conectado a tu repo **Santiagodiaz04/chatbot-api**. Cada vez que hagas **push** a la rama **principal**, Railway hará un nuevo deploy. Eso **no rompe** la conexión; es la forma correcta de actualizar.

---

## Opción 1: Ya tienes el repo clonado en tu PC

Si en algún momento clonaste el repo (por ejemplo en otra carpeta):

1. **Copia los archivos actualizados** desde `c:\xampp\htdocs\public_html\chatbot-api\` a la carpeta donde está clonado el repo (sustituye los que haya).
2. Abre **terminal** en esa carpeta del repo.
3. Ejecuta:
   ```bash
   git status
   git add .
   git commit -m "Fix CORS y mejoras"
   git push origin principal
   ```
4. En GitHub verás el nuevo commit. Railway detectará el push y hará un **nuevo deploy** automáticamente.

---

## Opción 2: Solo tienes la carpeta en public_html (no es un clone de GitHub)

Si tu carpeta `chatbot-api` **no** está conectada a GitHub (no hiciste `git clone` ahí):

### A) Conectar esta carpeta al repo de GitHub

1. Abre **terminal** (PowerShell o CMD) y ve a la carpeta del chatbot:
   ```bash
   cd c:\xampp\htdocs\public_html\chatbot-api
   ```
2. Si nunca has usado git aquí, inicia el repo y conecta el remoto:
   ```bash
   git init
   git remote add origin https://github.com/Santiagodiaz04/chatbot-api.git
   git branch -M principal
   ```
3. Trae el contenido actual del repo (por si hay algo que no tienes local):
   ```bash
   git pull origin principal --allow-unrelated-histories
   ```
   Si pide merge, acepta. Si hay conflictos, avisa.
4. Añade todo, haz commit y sube:
   ```bash
   git add .
   git commit -m "Actualizar API: CORS y mejoras"
   git push -u origin principal
   ```

### B) O: Clonar el repo en otra carpeta y copiar archivos

1. En otra ruta (por ejemplo Escritorio), clona el repo:
   ```bash
   cd %USERPROFILE%\Desktop
   git clone https://github.com/Santiagodiaz04/chatbot-api.git
   cd chatbot-api
   ```
2. Copia desde `c:\xampp\htdocs\public_html\chatbot-api\` todos los archivos (main.py, config.py, db.py, handlers.py, nlu.py, php_client.py, requirements.txt, Procfile, .env.example, etc.) **encima** de los del clone.
3. Sube los cambios:
   ```bash
   git add .
   git commit -m "Actualizar API: CORS y mejoras"
   git push origin principal
   ```

---

## Qué no hacer

- **No borres** el repo en GitHub.
- **No cambies** el nombre del repo ni la rama que Railway usa (normalmente **principal** o **main**).
- **No quites** la conexión del proyecto en Railway con GitHub.
- **No subas** el archivo `.env` (debe estar en .gitignore); en Railway se configuran las variables en la web.

---

## Después del push

1. Entra a **Railway** → tu proyecto → **Deployments**.
2. Debería aparecer un **nuevo deploy** (Trigger: GitHub push).
3. Espera a que termine (estado "Success" / "Running").
4. Prueba el chatbot en https://ctrbienesraices.com.

Si el deploy falla, revisa los **logs** en Railway para ver el error (por ejemplo falta un archivo o dependencia).
