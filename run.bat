@echo off
REM Iniciar API Chatbot CTR (Windows)
cd /d "%~dp0"
if not exist ".env" (
    echo Copia .env.example a .env y configura DB y PHP_BASE_URL.
    pause
    exit /b 1
)
if not exist ".venv" python -m venv .venv
call .venv\Scripts\activate.bat
.venv\Scripts\pip.exe install -r requirements.txt -q
.venv\Scripts\uvicorn.exe main:app --host 0.0.0.0 --port 8000 --reload
