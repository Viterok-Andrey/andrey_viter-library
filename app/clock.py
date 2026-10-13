"""Текущая дата сервиса.

Вынесена в отдельную функцию, чтобы её можно было зафиксировать
(переменная APP_TODAY) и тем самым сделать замеры и тесты воспроизводимыми.
"""
from datetime import date

from app import config


def today() -> date:
    if config.APP_TODAY:
        return date.fromisoformat(config.APP_TODAY)
    return date.today()
