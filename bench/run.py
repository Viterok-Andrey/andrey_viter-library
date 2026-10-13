"""Замеры времени ответа операций сервиса.

Запуск (сервис должен быть запущен, а в базе загружено нужное наполнение):

    python -m bench.run small      # метка «small»: замеры на малом объёме
    python -m bench.run work       # метка «work»: замеры на рабочем объёме

Условия измерения:
  * перед каждой серией выполняется прогрев (--warmup запросов), в расчёт он не входит;
  * в серии --repeats повторов (по заданию не меньше 20);
  * все запросы идут последовательно, по одному соединению, под одной учётной записью
    (APP_USER из .env);
  * время считается от отправки запроса до получения всего ответа, на стороне клиента.

Число запросов к базе, время, проведённое в базе, и время открытия соединения берутся
из заголовков ответа X-DB-Queries, X-DB-Time-Ms и X-DB-Connect-Ms, которые добавляет сервис.

Результат печатается и сохраняется в bench/results/<метка>.json.
"""
import argparse
import http.client
import json
import math
import platform
import os
import random
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

from app import clock, config
from app.db import connect

RESULTS_DIR = Path(__file__).resolve().parent / "results"
CARD_SEED = 1   


class Sample:
    """Результат одного запроса."""

    def __init__(self, status, body, ms, queries, db_ms, connect_ms):
        self.status = status
        self.body = body
        self.ms = ms
        self.queries = queries
        self.db_ms = db_ms
        self.connect_ms = connect_ms


class Client:
    """Простой HTTP-клиент с одним постоянным соединением."""

    def __init__(self, base_url: str):
        parsed = urlparse(base_url)
        self.connection = http.client.HTTPConnection(parsed.hostname, parsed.port or 80, timeout=120)
        self.token = None

    def request(self, method: str, path: str, body=None, expect: int = 200) -> Sample:
        headers = {"Content-Type": "application/json"}
        if self.token:
            headers["Authorization"] = "Bearer " + self.token
        payload = json.dumps(body) if body is not None else None

        started = time.perf_counter()
        self.connection.request(method, path, body=payload, headers=headers)
        response = self.connection.getresponse()
        raw = response.read()
        elapsed_ms = (time.perf_counter() - started) * 1000

        if response.status != expect:
            sys.exit(f"{method} {path}: ожидался код {expect}, получен {response.status}: {raw[:200]!r}")
        return Sample(
            status=response.status,
            body=json.loads(raw) if raw else None,
            ms=elapsed_ms,
            queries=int(response.getheader("X-DB-Queries", "0")),
            db_ms=float(response.getheader("X-DB-Time-Ms", "0")),
            connect_ms=float(response.getheader("X-DB-Connect-Ms", "0")),
        )


def percentile(sorted_values, p):
    """Процентиль методом ближайшего ранга."""
    rank = max(math.ceil(p / 100 * len(sorted_values)) - 1, 0)
    return sorted_values[rank]


def summarize(samples):
    times = sorted(s.ms for s in samples)
    return {
        "n": len(samples),
        "min": times[0],
        "p50": statistics.median(times),
        "p95": percentile(times, 95),
        "max": times[-1],
        "mean": statistics.fmean(times),
        "db_queries": statistics.median(s.queries for s in samples),
        "db_p50": statistics.median(s.db_ms for s in samples),
        "connect_p50": statistics.median(s.connect_ms for s in samples),
        # время в коде приложения: разность по каждому запросу, затем медиана
        "app_p50": statistics.median(s.ms - s.db_ms for s in samples),
    }


def pick_write_targets():
    """Свободный экземпляр и читатель без просрочек: на них проверяются выдача и возврат."""
    with connect() as conn:
        copy_id = conn.execute(
            "SELECT c.id FROM book_copy c WHERE NOT EXISTS "
            "(SELECT 1 FROM loan l WHERE l.copy_id = c.id AND l.returned_at IS NULL) "
            "ORDER BY c.id LIMIT 1"
        ).fetchone()["id"]
        reader_id = conn.execute(
            "SELECT r.id FROM reader r WHERE NOT EXISTS "
            "(SELECT 1 FROM loan l WHERE l.reader_id = r.id AND l.returned_at IS NULL "
            " AND l.due_date < %s) ORDER BY r.id LIMIT 1",
            (clock.today(),),
        ).fetchone()["id"]
    return copy_id, reader_id


def table_counts():
    with connect() as conn:
        return {
            table: conn.execute(f"SELECT count(*) AS n FROM {table}").fetchone()["n"]
            for table in ("reader", "book", "book_copy", "loan")
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Замеры времени ответа операций сервиса")
    parser.add_argument("label", help="метка серии: small или work")
    parser.add_argument("--url", default="http://localhost:8080", help="адрес сервиса")
    parser.add_argument("--repeats", type=int, default=40, help="повторов в серии (не меньше 20)")
    parser.add_argument("--warmup", type=int, default=5, help="запросов прогрева перед серией")
    args = parser.parse_args()
    if args.repeats < 20:
        sys.exit("По заданию в серии должно быть не меньше 20 повторов")

    counts_before = table_counts()
    total_loans = counts_before["loan"]
    page_size = 20
    middle_page = max(total_loans // page_size // 2, 1)
    rng = random.Random(CARD_SEED)
    card_ids = [rng.randint(1, total_loans) for _ in range(args.warmup + args.repeats)]
    copy_id, reader_id = pick_write_targets()

    client = Client(args.url)
    login = client.request("POST", "/api/login", {"username": config.APP_USER,
                                                  "password": config.APP_PASSWORD})
    client.token = login.body["token"]

    reads = [
        ("login", "POST /api/login",
         lambda i: client.request("POST", "/api/login", {"username": config.APP_USER,
                                                         "password": config.APP_PASSWORD})),
        ("list_first_page", f"GET /api/loans?page=1&size={page_size}",
         lambda i: client.request("GET", f"/api/loans?page=1&size={page_size}")),
        ("list_middle_page", f"GET /api/loans?page={middle_page}&size={page_size}",
         lambda i: client.request("GET", f"/api/loans?page={middle_page}&size={page_size}")),
        ("list_overdue", f"GET /api/loans?status=overdue&page=1&size={page_size}",
         lambda i: client.request("GET", f"/api/loans?status=overdue&page=1&size={page_size}")),
        ("list_by_reader", f"GET /api/loans?reader_id=25&size={page_size}",
         lambda i: client.request("GET", f"/api/loans?reader_id=25&size={page_size}")),
        ("loan_card", "GET /api/loans/{id}",
         lambda i: client.request("GET", f"/api/loans/{card_ids[i]}")),
        ("summary", "GET /api/summary",
         lambda i: client.request("GET", "/api/summary")),
    ]

    results = []
    for name, description, step in reads:
        print(f"  {name} ...", flush=True)
        for i in range(args.warmup):                 
            step(i)
        samples = [step(args.warmup + i) for i in range(args.repeats)]
        results.append({"name": name, "description": description, **summarize(samples)})

    print("  issue / return ...", flush=True)
    issue_samples, return_samples = [], []
    for i in range(args.warmup + args.repeats):
        issued = client.request("POST", "/api/loans",
                                {"reader_id": reader_id, "copy_id": copy_id}, expect=201)
        returned = client.request("POST", f"/api/loans/{issued.body['id']}/return")
        if i >= args.warmup:
            issue_samples.append(issued)
            return_samples.append(returned)
    results.append({"name": "issue", "description": "POST /api/loans", **summarize(issue_samples)})
    results.append({"name": "return", "description": "POST /api/loans/{id}/return",
                    **summarize(return_samples)})

    counts_after = table_counts()
    meta = {
        "label": args.label,
        "date": datetime.now().isoformat(timespec="seconds"),
        "url": args.url,
        "user": config.APP_USER,
        "repeats": args.repeats,
        "warmup": args.warmup,
        "page_size": page_size,
        "app_today": config.APP_TODAY or "(текущая дата)",
        "machine": f"{platform.platform()}, {platform.processor() or 'процессор не определён'}, "
                   f"логических ядер: {os.cpu_count()}",
        "python": platform.python_version(),
        "rows_before": counts_before,
        "rows_after": counts_after,
        "loans_added_by_measurement": counts_after["loan"] - counts_before["loan"],
        "write_targets": {"reader_id": reader_id, "copy_id": copy_id},
    }

    RESULTS_DIR.mkdir(exist_ok=True)
    out = RESULTS_DIR / f"{args.label}.json"
    out.write_text(json.dumps({"meta": meta, "operations": results}, ensure_ascii=False, indent=2),
                   encoding="utf-8")

    print(f"\nСерия «{args.label}»: прогрев {args.warmup}, повторов {args.repeats}")
    print(f"Строк в таблицах: {counts_before}")
    print(f"Записей выдач добавлено замером: {meta['loans_added_by_measurement']}\n")
    print(f"{'операция':18} {'p50':>9} {'p95':>9} {'max':>9} {'в базе':>9} {'соедин.':>9} {'запросов':>9}")
    for r in results:
        print(f"{r['name']:18} {r['p50']:9.2f} {r['p95']:9.2f} {r['max']:9.2f} "
              f"{r['db_p50']:9.2f} {r['connect_p50']:9.2f} {r['db_queries']:9.0f}")
    print(f"\nСохранено: {out}")


if __name__ == "__main__":
    main()
