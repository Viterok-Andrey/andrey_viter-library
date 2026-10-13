"""Настройки сервиса. Всё берётся из переменных окружения (файл .env)."""
import os
import re

from dotenv import load_dotenv

load_dotenv()


def _check_identifier(value: str, name: str) -> str:
    if not re.fullmatch(r"[a-z][a-z0-9_]*", value):
        raise ValueError(
            f"{name} должен состоять из строчных латинских букв, цифр и '_': {value!r}"
        )
    return value


PREFIX = _check_identifier(os.getenv("PREFIX", "name_surname"), "PREFIX")

DB_USER = os.getenv("DB_USER", "app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{PREFIX}",
)

SCHEMA = _check_identifier(os.getenv("DB_SCHEMA", PREFIX), "DB_SCHEMA")

APP_USER = os.getenv("APP_USER", "demo")
APP_PASSWORD = os.getenv("APP_PASSWORD", "demo")
SECRET_KEY = os.getenv("SECRET_KEY", "changeme")
TOKEN_TTL_SECONDS = 8 * 60 * 60 

APP_TODAY = os.getenv("APP_TODAY", "").strip()
