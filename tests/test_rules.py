"""Тесты бизнес-правил: просрочка, штраф, запрет выдачи."""
from datetime import date

import pytest

from app import rules


def test_due_date_is_14_days_after_issue():
    assert rules.due_date_for(date(2026, 9, 1)) == date(2026, 9, 15)


def test_returned_on_due_date_has_no_overdue():
    assert rules.overdue_days(date(2026, 9, 15), date(2026, 9, 15)) == 0


def test_returned_early_has_no_overdue():
    assert rules.overdue_days(date(2026, 9, 15), date(2026, 9, 10)) == 0


def test_overdue_days_is_difference_between_dates():
    assert rules.overdue_days(date(2026, 9, 15), date(2026, 9, 20)) == 5


def test_fine_is_days_times_rate():
    assert rules.fine_for(5) == 5 * rules.FINE_PER_DAY


def test_no_overdue_means_no_fine():
    assert rules.fine_for(0) == 0


def test_cannot_issue_copy_that_is_already_on_hands():
    with pytest.raises(rules.CopyNotAvailable):
        rules.check_can_issue(copy_is_free=False, reader_overdue_count=0)


def test_cannot_issue_to_reader_with_overdue_loans():
    with pytest.raises(rules.ReaderHasOverdue):
        rules.check_can_issue(copy_is_free=True, reader_overdue_count=1)


def test_can_issue_free_copy_to_reader_without_debts():
    rules.check_can_issue(copy_is_free=True, reader_overdue_count=0)
