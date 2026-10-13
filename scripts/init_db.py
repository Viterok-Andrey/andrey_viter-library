"""Создаёт схему с префиксом и таблицы. Запуск: python -m scripts.init_db

ВНИМАНИЕ: схема пересоздаётся с нуля, все данные в ней удаляются.
"""
from app import config
from app.db import apply_schema


def main() -> None:
    apply_schema(config.SCHEMA)
    print(f"Схема {config.SCHEMA} создана")


if __name__ == "__main__":
    main()
