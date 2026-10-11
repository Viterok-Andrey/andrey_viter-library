"""
Бизнес-правила библиотеки.
"""
from datetime import date, timedelta

LOAN_DAYS = 14
FINE_PER_DAY = 100


class LoanError(Exception):
    """Выдача невозможна."""


class CopyNotAvailable(LoanError):
    """Экземпляр уже на руках у другого читателя."""


class ReaderHasOverdue(LoanError):
    """У читателя есть просроченные выдачи."""


def due_date_for(issued_at: date) -> date:
    """Срок возврата для книги, выданной в указанный день."""
    return issued_at + timedelta(days=LOAN_DAYS)


def overdue_days(due_date: date, actual_date: date) -> int:
    """Сколько дней просрочки: разница между фактической датой и сроком.

    Вернули вовремя или раньше срока: 0 (отрицательной просрочки не бывает).
    """
    return max((actual_date - due_date).days, 0)


def fine_for(days: int) -> int:
    """Размер штрафа за указанное число дней просрочки."""
    return days * FINE_PER_DAY


def check_can_issue(copy_is_free: bool, reader_overdue_count: int) -> None:
    """Проверяет, можно ли выдать экземпляр читателю.

    Выдать можно, только если экземпляр свободен и у читателя нет
    просроченных выдач. Если нельзя, бросается исключение.
    """
    if not copy_is_free:
        raise CopyNotAvailable("экземпляр уже выдан")
    if reader_overdue_count > 0:
        raise ReaderHasOverdue("у читателя есть просроченные выдачи")
