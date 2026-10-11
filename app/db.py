"""Подключение к PostgreSQL."""
import psycopg

from app import config


def connect(use_schema: bool = True) -> psycopg.Connection:
    options = f"-c search_path={config.SCHEMA}" if use_schema else None
    return psycopg.connect(config.DATABASE_URL, options=options)
