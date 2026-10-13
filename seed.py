"""Наполнение базы данных. Запуск:

    python seed.py small    # малое наполнение (~300 выдач)
    python seed.py work     # рабочее наполнение (~75 000 выдач)

Повторный запуск даёт ровно те же данные: генератор случайных чисел
инициализируется числом 42, а «сегодняшняя» дата зафиксирована в коде.
Перед наполнением таблицы очищаются.
"""
import random
import sys
from datetime import date, timedelta

from app.db import connect
from app.rules import due_date_for, fine_for, overdue_days

SEED = 42

REF_DATE = date(2026, 10, 11)

SIZES = {
    "small": {"readers": 50, "books": 100, "copies": 200, "loans": 300, "history_days": 90},
    "work": {"readers": 3000, "books": 10000, "copies": 30000, "loans": 75000, "history_days": 730},
}

from seed_data import CLASSIC_BOOKS, FEMALE_NAMES, MALE_NAMES, PUBLISHERS, SURNAMES


OPEN_WINDOW_DAYS = 17
OPEN_SHARE = 0.6         
LATE_SHARE = 0.2         


def make_readers(rng, n):
    readers = []
    for i in range(1, n + 1):
        male_surname, female_surname = rng.choice(SURNAMES)
        if rng.random() < 0.5:
            full_name = f"{male_surname} {rng.choice(MALE_NAMES)}"
        else:
            full_name = f"{female_surname} {rng.choice(FEMALE_NAMES)}"
        readers.append((full_name, f"R{i:06d}"))
    return readers


def make_books(rng, n):
    """Книги берутся из списка классики. Когда список заканчивается (рабочее
    наполнение), названия повторяются как другие издания: «Название (издательство, год)»."""
    classics = list(CLASSIC_BOOKS)
    rng.shuffle(classics)               
    books = []
    for i in range(n):
        title, author = classics[i % len(classics)]
        if i >= len(classics):
            title = f"{title} ({rng.choice(PUBLISHERS)}, {rng.randint(1950, 2024)})"
        books.append((title, author))
    return books


def make_copies(n_copies, n_books):
    return [((i % n_books) + 1, f"INV-{i + 1:06d}") for i in range(n_copies)]


def make_loans(rng, n_loans, n_readers, n_copies, history_days):
    """Строит историю выдач за history_days дней так, чтобы у одного экземпляра они не пересекались.

    Выдачи с даты REF_DATE - OPEN_WINDOW_DAYS с вероятностью OPEN_SHARE остаются «на руках»:
    часть из них к REF_DATE уже просрочена, часть ещё в сроке. Все более ранние выдачи
    возвращены. Большинство возвратов приходится на срок, меньшая часть (LATE_SHARE) с опозданием.
    """
    busy = [[] for _ in range(n_copies + 1)]   
    history_start = REF_DATE - timedelta(days=history_days)
    open_from = REF_DATE - timedelta(days=OPEN_WINDOW_DAYS)
    loans = []
    attempts = 0
    while len(loans) < n_loans and attempts < n_loans * 30:
        attempts += 1
        copy_id = rng.randint(1, n_copies)
        issued = history_start + timedelta(days=rng.randint(0, history_days - 2))
        due = due_date_for(issued)

        returned = None
        end = date.max                             
        stays_open = issued >= open_from and rng.random() < OPEN_SHARE
        if not stays_open:
            if rng.random() < LATE_SHARE:
                days_out = rng.randint(15, 35)   
            else:
                days_out = rng.randint(1, 14)      
            returned = min(issued + timedelta(days=days_out), REF_DATE)   # не позже REF_DATE
            end = returned

        if any(issued <= b_end and b_start <= end for b_start, b_end in busy[copy_id]):
            continue                              
        busy[copy_id].append((issued, end))

        fine = fine_for(overdue_days(due, returned)) if returned else 0
        loans.append((rng.randint(1, n_readers), copy_id, issued, due, returned, fine))

    loans.sort(key=lambda row: row[2])             
    return loans


def fill(cur, table, columns, rows):
    """Быстрая загрузка через COPY."""
    with cur.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def main() -> None:
    size = sys.argv[1] if len(sys.argv) > 1 else "small"
    if size not in SIZES:
        sys.exit(f"Использование: python seed.py [{'|'.join(SIZES)}]")
    cfg = SIZES[size]


    readers = make_readers(random.Random(SEED), cfg["readers"])
    books = make_books(random.Random(SEED + 1), cfg["books"])
    copies = make_copies(cfg["copies"], cfg["books"])
    loans = make_loans(random.Random(SEED + 2), cfg["loans"], cfg["readers"], cfg["copies"],
                       cfg["history_days"])

    with connect() as conn:
        with conn.cursor() as cur:
            cur.execute("TRUNCATE loan, book_copy, book, reader RESTART IDENTITY")
            fill(cur, "reader", ["full_name", "card_number"], readers)
            fill(cur, "book", ["title", "author"], books)
            fill(cur, "book_copy", ["book_id", "inventory_number"], copies)
            fill(cur, "loan",
                 ["reader_id", "copy_id", "issued_at", "due_date", "returned_at", "fine"],
                 loans)
            cur.execute("ANALYZE")
            print(f"Наполнение «{size}» загружено. Строк в таблицах:")
            for table in ("reader", "book", "book_copy", "loan"):
                cur.execute(f"SELECT count(*) AS n FROM {table}")
                print(f"  {table:10} {cur.fetchone()['n']}")
            cur.execute("SELECT count(*) AS n FROM loan WHERE returned_at IS NULL")
            on_hands = cur.fetchone()["n"]
            cur.execute(
                "SELECT count(*) AS n FROM loan WHERE returned_at IS NULL AND due_date < %s",
                (REF_DATE,),
            )
            print(f"  на руках: {on_hands}, из них просрочено на {REF_DATE}: {cur.fetchone()['n']}")


if __name__ == "__main__":
    main()
