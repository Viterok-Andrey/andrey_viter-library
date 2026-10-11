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
REF_DATE = date(2026, 9, 1)
HISTORY_START = REF_DATE - timedelta(days=730)

SIZES = {
    "small": {"readers": 50, "books": 100, "copies": 200, "loans": 300},
    "work": {"readers": 3000, "books": 10000, "copies": 30000, "loans": 75000},
}

FIRST_NAMES = ["Иван", "Пётр", "Алексей", "Дмитрий", "Сергей", "Андрей", "Михаил",
               "Анна", "Мария", "Елена", "Ольга", "Наталья", "Татьяна", "Ирина"]
LAST_NAMES = ["Иванов", "Петров", "Сидоров", "Смирнов", "Кузнецов", "Попов",
              "Васильев", "Соколов", "Михайлов", "Новиков", "Фёдоров", "Морозов",
              "Волков", "Алексеев", "Лебедев", "Семёнов", "Егоров", "Павлов"]
TITLE_WORDS = ["Тайна", "Дорога", "Город", "Ночь", "Сад", "Море", "Звезда", "Остров",
               "Письмо", "Дом", "Река", "Лес", "Гора", "Время", "Сон", "Ветер"]
TITLE_ADJ = ["старого", "забытого", "тихого", "дальнего", "северного", "золотого",
             "последнего", "пустого", "зимнего", "светлого"]
AUTHORS = ["А. Белов", "Б. Громов", "В. Дымов", "Г. Ершов", "Д. Жуков", "Е. Зайцев",
           "Ж. Исаев", "З. Комаров", "И. Лосев", "К. Мартынов", "Л. Назаров",
           "М. Орлов", "Н. Прохоров", "О. Рябов", "П. Свиридов", "Р. Тихонов"]

RECENT_DAYS = 45       
OPEN_SHARE = 0.6      


def make_readers(rng, n):
    return [
        (f"{rng.choice(LAST_NAMES)} {rng.choice(FIRST_NAMES)}", f"R{i:06d}")
        for i in range(1, n + 1)
    ]


def make_books(rng, n):
    return [
        (f"{rng.choice(TITLE_WORDS)} {rng.choice(TITLE_ADJ)} {rng.choice(TITLE_WORDS).lower()} {i}",
         rng.choice(AUTHORS))
        for i in range(1, n + 1)
    ]


def make_copies(n_copies, n_books):
    return [((i % n_books) + 1, f"INV-{i + 1:06d}") for i in range(n_copies)]


def make_loans(rng, n_loans, n_readers, n_copies):
    """Строит историю выдач за два года так, чтобы у одного экземпляра они не пересекались.

    Недавние выдачи (последние RECENT_DAYS дней) с вероятностью OPEN_SHARE
    остаются «на руках»: часть из них к REF_DATE уже просрочена, часть нет.
    """
    busy = [[] for _ in range(n_copies + 1)]   
    history_days = (REF_DATE - HISTORY_START).days
    loans = []
    attempts = 0
    while len(loans) < n_loans and attempts < n_loans * 30:
        attempts += 1
        copy_id = rng.randint(1, n_copies)
        issued = HISTORY_START + timedelta(days=rng.randint(0, history_days - 2))
        due = due_date_for(issued)

        returned = None
        if issued >= REF_DATE - timedelta(days=RECENT_DAYS) and rng.random() < OPEN_SHARE:
            end = date.max                     
        else:
            returned = issued + timedelta(days=rng.randint(1, 35))
            if returned > REF_DATE:
                returned = None                  
                end = date.max
            else:
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
    rng = random.Random(SEED)

    readers = make_readers(rng, cfg["readers"])
    books = make_books(rng, cfg["books"])
    copies = make_copies(cfg["copies"], cfg["books"])
    loans = make_loans(rng, cfg["loans"], cfg["readers"], cfg["copies"])

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
                cur.execute(f"SELECT count(*) FROM {table}")
                print(f"  {table:10} {cur.fetchone()[0]}")
            cur.execute("SELECT count(*) FROM loan WHERE returned_at IS NULL")
            on_hands = cur.fetchone()[0]
            cur.execute(
                "SELECT count(*) FROM loan WHERE returned_at IS NULL AND due_date < %s",
                (REF_DATE,),
            )
            print(f"  на руках: {on_hands}, из них просрочено на {REF_DATE}: {cur.fetchone()[0]}")


if __name__ == "__main__":
    main()
