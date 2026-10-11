"""Создаёт схему с префиксом и таблицы. Запуск: python -m scripts.init_db

"""
from pathlib import Path

from app import config
from app.db import connect

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


def main() -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    sql = sql.replace("{{schema}}", config.SCHEMA)
    with connect(use_schema=False) as conn:
        conn.execute(sql)
    print(f"Схема {config.SCHEMA} создана")


if __name__ == "__main__":
    main()
