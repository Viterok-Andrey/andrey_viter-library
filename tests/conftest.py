"""Общие подготовки для тестов операций API.

Тесты работают в отдельной схеме <префикс>_test: рабочие данные не затрагиваются.
Перед каждым тестом схема заполняется одним и тем же маленьким набором данных,
поэтому тесты не зависят ни от порядка запуска, ни от ручной подготовки.
Для них должна быть запущена база данных (docker compose up -d).
"""
from datetime import date

import pytest
from fastapi.testclient import TestClient

from app import clock, config
from app.db import apply_schema, connect
from app.main import app

TODAY = date(2026, 9, 1)

READERS = [
    (1, "Иванов Иван", "R000001"),   
    (2, "Петров Пётр", "R000002"),   
    (3, "Сидоров Сидор", "R000003"),  
]
BOOKS = [(1, "Книга А", "Автор 1"), (2, "Книга Б", "Автор 2")]
COPIES = [  # id, book_id, инвентарный номер
    (1, 1, "INV-1"),   
    (2, 1, "INV-2"),   
    (3, 2, "INV-3"),   
    (4, 2, "INV-4"),   
    (5, 1, "INV-5"),   
]
LOANS = [  # id, reader, copy, выдана, срок, возвращена, штраф
    (1, 2, 2, date(2026, 8, 1), date(2026, 8, 15), None, 0),                
    (2, 3, 3, date(2026, 8, 10), date(2026, 8, 24), date(2026, 8, 20), 0),  
    (3, 3, 4, date(2026, 8, 1), date(2026, 8, 15), date(2026, 8, 20), 50),     
    (4, 1, 1, date(2026, 8, 25), date(2026, 9, 8), None, 0),                  
    (5, 3, 5, date(2026, 7, 1), date(2026, 7, 15), date(2026, 7, 10), 0),     
]


@pytest.fixture(scope="session")
def test_schema():
    """Создаёт тестовую схему один раз за весь прогон."""
    name = f"{config.PREFIX}_test"
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(config, "SCHEMA", name)
        apply_schema(name)
        yield name


@pytest.fixture
def db_ready(test_schema, monkeypatch):
    """Перед тестом: подменяет схему и дату, очищает таблицы и заливает тестовые данные."""
    monkeypatch.setattr(config, "SCHEMA", test_schema)
    monkeypatch.setattr(clock, "today", lambda: TODAY)
    with connect() as conn:
        conn.execute("TRUNCATE loan, book_copy, book, reader RESTART IDENTITY CASCADE")
        for row in READERS:
            conn.execute("INSERT INTO reader (id, full_name, card_number) VALUES (%s, %s, %s)", row)
        for row in BOOKS:
            conn.execute("INSERT INTO book (id, title, author) VALUES (%s, %s, %s)", row)
        for row in COPIES:
            conn.execute("INSERT INTO book_copy (id, book_id, inventory_number) VALUES (%s, %s, %s)", row)
        for row in LOANS:
            conn.execute(
                "INSERT INTO loan (id, reader_id, copy_id, issued_at, due_date, returned_at, fine) "
                "VALUES (%s, %s, %s, %s, %s, %s, %s)",
                row,
            )
        for table in ("reader", "book", "book_copy", "loan"):
            conn.execute(
                f"SELECT setval(pg_get_serial_sequence('{table}', 'id'), (SELECT max(id) FROM {table}))"
            )


@pytest.fixture
def client(db_ready):
    """Клиент без авторизации."""
    return TestClient(app)


@pytest.fixture
def auth(client):
    """Заголовок авторизации, полученный обычным входом."""
    response = client.post(
        "/api/login", json={"username": config.APP_USER, "password": config.APP_PASSWORD}
    )
    return {"Authorization": "Bearer " + response.json()["token"]}
