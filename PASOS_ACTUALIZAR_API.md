# Pasos para actualizar la API del chatbot (rama main)

Cada vez que hagas **push** a **main**, Railway hará un nuevo deploy automáticamente.

---

## Paso a paso (desde la carpeta chatbot-api)

### 1. Abrir terminal en la carpeta del chatbot

- Abre **PowerShell** o **CMD**.
- Ve a la carpeta:
  ```powershell
  cd c:\xampp\htdocs\public_html\chatbot-api
  ```

### 2. Ver qué archivos cambiaron

```powershell
git status
```

Verás los archivos modificados (por ejemplo `db.py`, `handlers.py`, `nlu.py`).

### 3. Añadir todos los cambios

```powershell
git add .
```

(O solo algunos: `git add db.py handlers.py nlu.py`)

### 4. Hacer commit con un mensaje claro

```powershell
git commit -m "Actualizar API: qué es Ibiza, búsqueda por nombre, extract_nombre"
```

### 5. Subir a GitHub (rama main)

```powershell
git push origin main
```

Si te pide usuario/contraseña, usa tu usuario de GitHub y un **Personal Access Token** (no la contraseña de la cuenta). Si ya tienes credenciales guardadas, no pedirá nada.

### 6. Comprobar en Railway

1. Entra a **Railway** → tu proyecto del chatbot.
2. Pestaña **Deployments**: debe aparecer un nuevo deploy (trigger: GitHub push).
3. Espera a que termine en **Success** / **Running**.
4. Prueba el chatbot en tu web (o en la URL de la API).

---

## Resumen rápido (copiar y pegar)

```powershell
cd c:\xampp\htdocs\public_html\chatbot-api
git add .
git commit -m "Actualizar API: qué es Ibiza, búsqueda por nombre, extract_nombre"
git push origin main
```

---

## Si algo falla

- **"Nothing to commit"**: No hay cambios; ya está todo subido o no guardaste los archivos.
- **"Failed to push"**: Revisa que tengas permisos en el repo y que la rama sea `main`. Si el remoto tiene cambios que tú no tienes, haz antes: `git pull origin main` y luego otra vez `git push origin main`.
- **Railway no despliega**: En Railway → Settings, comprueba que esté conectado al repo correcto y a la rama **main**.
