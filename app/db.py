"""Подключение к PostgreSQL и выполнение запросов.

Все запросы сервиса идут через fetch_all / fetch_one / execute. Благодаря этому
для каждого обращения к сервису можно посчитать, сколько запросов выполнено
и сколько времени ушло на них в базе данных (см. подраздел 2.6 методички).
"""
from contextvars import ContextVar
from pathlib import Path
from time import perf_counter

import psycopg
from psycopg.rows import dict_row

from app import config

SCHEMA_FILE = Path(__file__).resolve().parent.parent / "db" / "schema.sql"


class QueryStats:
    """Счётчик запросов к базе в рамках одного обращения к сервису."""

    def __init__(self) -> None:
        self.queries = 0
        self.seconds = 0.0         
        self.connect_seconds = 0.0   


_current_stats: ContextVar = ContextVar("query_stats", default=None)


def start_stats() -> QueryStats:
    stats = QueryStats()
    _current_stats.set(stats)
    return stats


def connect(use_schema: bool = True) -> psycopg.Connection:
    options = f"-c search_path={config.SCHEMA}" if use_schema else None
    started = perf_counter()
    conn = psycopg.connect(config.DATABASE_URL, options=options, row_factory=dict_row)
    stats = _current_stats.get()
    if stats is not None:
        stats.connect_seconds += perf_counter() - started
    return conn


def _run(conn: psycopg.Connection, sql: str, params, fetch: str):
    started = perf_counter()
    cur = conn.execute(sql, params)
    if fetch == "all":
        result = cur.fetchall()
    elif fetch == "one":
        result = cur.fetchone()
    else:
        result = None
    stats = _current_stats.get()
    if stats is not None:
        stats.queries += 1
        stats.seconds += perf_counter() - started
    return result


def fetch_all(conn, sql: str, params=()) -> list:
    return _run(conn, sql, params, "all")


def fetch_one(conn, sql: str, params=()):
    return _run(conn, sql, params, "one")


def execute(conn, sql: str, params=()) -> None:
    _run(conn, sql, params, "none")


def apply_schema(schema: str) -> None:
    sql = SCHEMA_FILE.read_text(encoding="utf-8")
    sql = sql.replace("{{schema}}", schema)
    with connect(use_schema=False) as conn:
        conn.execute(sql)
