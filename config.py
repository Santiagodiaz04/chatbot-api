# config.py - Configuración API Chatbot CTR
"""Carga variables desde .env. Misma DB que PHP."""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_NAME = os.getenv("DB_NAME", "ctr_bienes_raices")
DB_USER = os.getenv("DB_USER", "root")
DB_PASS = os.getenv("DB_PASS", "")
DB_CHARSET = "utf8mb4"

PHP_BASE_URL = os.getenv("PHP_BASE_URL", "http://localhost/public_html").rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

CORS_ORIGINS_STR = os.getenv("CORS_ORIGINS", "http://localhost,http://127.0.0.1")
CORS_ORIGINS = [o.strip() for o in CORS_ORIGINS_STR.split(",") if o.strip()]
