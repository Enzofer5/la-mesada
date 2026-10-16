"""Configuración de la aplicación. Todos los valores sensibles se leen de variables de entorno (.env)."""
import os
from datetime import timedelta

from dotenv import load_dotenv

BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
load_dotenv(os.path.join(BASE_DIR, ".env"))


def _bool(valor, defecto=False):
    if valor is None:
        return defecto
    return str(valor).strip().lower() in ("1", "true", "si", "sí", "yes", "on")


def _database_url():
    url = os.getenv("DATABASE_URL")
    if url:
        return url
    usuario = os.getenv("DB_USER", "lamesada")
    clave = os.getenv("DB_PASSWORD", "")
    host = os.getenv("DB_HOST", "localhost")
    puerto = os.getenv("DB_PORT", "3306")
    nombre = os.getenv("DB_NAME", "la_mesada")
    return f"mysql+pymysql://{usuario}:{clave}@{host}:{puerto}/{nombre}?charset=utf8mb4"


class Config:
    APP_NOMBRE = os.getenv("APP_NOMBRE", "La Mesada")
    APP_SUBTITULO = os.getenv("APP_SUBTITULO", "Sistema de Gestión Agrícola")

    SECRET_KEY = os.getenv("SECRET_KEY") or "cambiar-esta-clave-en-produccion"

    SQLALCHEMY_DATABASE_URI = _database_url()
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SQLALCHEMY_ENGINE_OPTIONS = {"pool_pre_ping": True, "pool_recycle": 280}

    # Sesiones seguras
    SESSION_COOKIE_HTTPONLY = True
    SESSION_COOKIE_SAMESITE = "Lax"
    SESSION_COOKIE_SECURE = _bool(os.getenv("SESSION_COOKIE_SECURE"), False)
    REMEMBER_COOKIE_HTTPONLY = True
    REMEMBER_COOKIE_SECURE = SESSION_COOKIE_SECURE
    REMEMBER_COOKIE_DURATION = timedelta(days=14)
    PERMANENT_SESSION_LIFETIME = timedelta(hours=int(os.getenv("SESSION_HORAS", "12")))

    # CSRF
    WTF_CSRF_TIME_LIMIT = None  # el token vive lo que dura la sesión (cómodo para el campo)

    # Archivos subidos
    UPLOAD_FOLDER = os.getenv("UPLOAD_FOLDER", os.path.join(BASE_DIR, "uploads"))
    MAX_CONTENT_LENGTH = int(os.getenv("MAX_UPLOAD_MB", "10")) * 1024 * 1024
    EXTENSIONES_PERMITIDAS = {"pdf", "jpg", "jpeg", "png", "webp", "doc", "docx", "xls", "xlsx", "csv", "txt"}

    POR_PAGINA = int(os.getenv("POR_PAGINA", "25"))
    MAX_INTENTOS_LOGIN = 5
    MINUTOS_BLOQUEO = 15


class TestConfig(Config):
    TESTING = True
    WTF_CSRF_ENABLED = False
    SQLALCHEMY_DATABASE_URI = os.getenv("TEST_DATABASE_URL", "sqlite:///:memory:")
    SQLALCHEMY_ENGINE_OPTIONS = {}
    UPLOAD_FOLDER = os.path.join(BASE_DIR, "tests", "_uploads")
