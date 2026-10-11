"""Настройки сервиса. Всё берётся из переменных окружения (файл .env)."""
import os
import re

from dotenv import load_dotenv

load_dotenv()

PREFIX = os.getenv("PREFIX", "name_surname")

if not re.fullmatch(r"[a-z][a-z0-9_]*", PREFIX):
    raise ValueError(
        f"PREFIX должен состоять из строчных латинских букв, цифр и '_': {PREFIX!r}"
    )

DB_USER = os.getenv("DB_USER", "app")
DB_PASSWORD = os.getenv("DB_PASSWORD", "changeme")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

DATABASE_URL = os.getenv(
    "DATABASE_URL",
    f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{PREFIX}",
)

SCHEMA = PREFIX
