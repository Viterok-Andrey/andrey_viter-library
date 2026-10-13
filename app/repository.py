"""SQL-запросы сервиса. Каждая функция получает открытое соединение conn."""
from app import clock
from app.db import execute, fetch_all, fetch_one
from app.rules import check_can_issue, due_date_for, fine_for, overdue_days


class NotFound(Exception):
    """Запрошенной записи нет в базе."""


class AlreadyReturned(Exception):
    """Экземпляр по этой выдаче уже возвращён."""


LOAN_SELECT = """
    SELECT l.id, l.issued_at, l.due_date, l.returned_at, l.fine,
           r.id AS reader_id, r.full_name, r.card_number,
           c.id AS copy_id, c.inventory_number,
           b.id AS book_id, b.title, b.author
    FROM loan l
    JOIN reader r ON r.id = l.reader_id
    JOIN book_copy c ON c.id = l.copy_id
    JOIN book b ON b.id = c.book_id
"""

STATUS_FILTERS = {
    "all": ("TRUE", False),
    "on_hands": ("l.returned_at IS NULL", False),
    "overdue": ("l.returned_at IS NULL AND l.due_date < %s", True),  
    "returned": ("l.returned_at IS NOT NULL", False),
}


def loan_status(returned_at, due_date) -> str:
    if returned_at is not None:
        return "returned"
    if due_date < clock.today():
        return "overdue"
    return "on_hands"


def _loan_card(row) -> dict:
    """Превращает строку запроса LOAN_SELECT в ответ API."""
    if row["returned_at"] is None:
        fine = fine_for(overdue_days(row["due_date"], clock.today()))
    else:
        fine = int(row["fine"])
    return {
        "id": row["id"],
        "status": loan_status(row["returned_at"], row["due_date"]),
        "issued_at": row["issued_at"],
        "due_date": row["due_date"],
        "returned_at": row["returned_at"],
        "fine": fine,
        "reader": {
            "id": row["reader_id"],
            "full_name": row["full_name"],
            "card_number": row["card_number"],
        },
        "copy": {"id": row["copy_id"], "inventory_number": row["inventory_number"]},
        "book": {"id": row["book_id"], "title": row["title"], "author": row["author"]},
    }


def list_loans(conn, page: int, size: int, status: str, reader_id=None) -> dict:
    condition, needs_today = STATUS_FILTERS[status]
    where = [condition]
    params = [clock.today()] if needs_today else []
    if reader_id is not None:
        where.append("l.reader_id = %s")
        params.append(reader_id)
    where_sql = " AND ".join(where)

    total = fetch_one(conn, f"SELECT count(*) AS n FROM loan l WHERE {where_sql}", params)["n"]
    rows = fetch_all(
        conn,
        f"{LOAN_SELECT} WHERE {where_sql} ORDER BY l.issued_at DESC, l.id DESC LIMIT %s OFFSET %s",
        params + [size, (page - 1) * size],
    )
    items = []
    for row in rows:
        loan = _loan_card(row)
        # в списке достаточно плоских полей, вложенные объекты нужны только карточке
        items.append({
            "id": loan["id"],
            "status": loan["status"],
            "reader_name": row["full_name"],
            "book_title": row["title"],
            "inventory_number": row["inventory_number"],
            "issued_at": loan["issued_at"],
            "due_date": loan["due_date"],
            "returned_at": loan["returned_at"],
            "fine": loan["fine"],
        })
    return {"items": items, "total": total, "page": page, "size": size}


def get_loan(conn, loan_id: int):
    """Карточка выдачи или None, если такой выдачи нет."""
    row = fetch_one(conn, f"{LOAN_SELECT} WHERE l.id = %s", (loan_id,))
    return _loan_card(row) if row else None


def issue_loan(conn, reader_id: int, copy_id: int):
    """Выдаёт экземпляр читателю.

    Возвращает карточку новой выдачи. Если читателя или экземпляра нет, бросает NotFound.
    Если выдать нельзя по правилам, бросает исключение из app.rules.
    """
    if fetch_one(conn, "SELECT id FROM reader WHERE id = %s", (reader_id,)) is None:
        raise NotFound("читатель не найден")
    if fetch_one(conn, "SELECT id FROM book_copy WHERE id = %s FOR UPDATE", (copy_id,)) is None:
        raise NotFound("экземпляр не найден")

    on_hands = fetch_one(
        conn, "SELECT count(*) AS n FROM loan WHERE copy_id = %s AND returned_at IS NULL", (copy_id,)
    )["n"]
    overdue = fetch_one(
        conn,
        "SELECT count(*) AS n FROM loan "
        "WHERE reader_id = %s AND returned_at IS NULL AND due_date < %s",
        (reader_id, clock.today()),
    )["n"]
    check_can_issue(copy_is_free=(on_hands == 0), reader_overdue_count=overdue)

    issued_at = clock.today()
    new = fetch_one(
        conn,
        "INSERT INTO loan (reader_id, copy_id, issued_at, due_date) "
        "VALUES (%s, %s, %s, %s) RETURNING id",
        (reader_id, copy_id, issued_at, due_date_for(issued_at)),
    )
    return get_loan(conn, new["id"])


def return_loan(conn, loan_id: int):
    """Принимает возврат и возвращает карточку выдачи.

    Бросает NotFound, если выдачи нет, и AlreadyReturned, если её уже закрыли.
    """
    row = fetch_one(
        conn, "SELECT id, due_date, returned_at FROM loan WHERE id = %s FOR UPDATE", (loan_id,)
    )
    if row is None:
        raise NotFound("выдача не найдена")
    if row["returned_at"] is not None:
        raise AlreadyReturned("экземпляр уже возвращён")

    today = clock.today()
    fine = fine_for(overdue_days(row["due_date"], today))
    execute(conn, "UPDATE loan SET returned_at = %s, fine = %s WHERE id = %s", (today, fine, loan_id))
    return get_loan(conn, loan_id)


def get_summary(conn) -> dict:
    """Сводка по всем данным: сколько экземпляров на руках, сколько просрочено, топ книг."""
    counts = fetch_one(
        conn,
        "SELECT count(*) FILTER (WHERE returned_at IS NULL) AS on_hands, "
        "       count(*) FILTER (WHERE returned_at IS NULL AND due_date < %s) AS overdue "
        "FROM loan",
        (clock.today(),),
    )
    top = fetch_all(
        conn,
        "SELECT b.id AS book_id, b.title, b.author, count(*) AS loans_count "
        "FROM loan l "
        "JOIN book_copy c ON c.id = l.copy_id "
        "JOIN book b ON b.id = c.book_id "
        "GROUP BY b.id, b.title, b.author "
        "ORDER BY loans_count DESC, b.id "
        "LIMIT 10",
    )
    return {
        "on_hands": counts["on_hands"],
        "overdue": counts["overdue"],
        "top_books": [
            {"book_id": t["book_id"], "title": t["title"], "author": t["author"],
             "loans_count": t["loans_count"]}
            for t in top
        ],
    }
