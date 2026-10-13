"""Сводные таблицы для отчёта по результатам двух серий замеров.

    python -m bench.report

"""
import json
import sys
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent / "results"


def load(label):
    path = RESULTS_DIR / f"{label}.json"
    if not path.exists():
        sys.exit(f"Нет файла {path}. Сначала выполните: python -m bench.run {label}")
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> None:
    small, work = load("small"), load("work")
    small_ops = {op["name"]: op for op in small["operations"]}

    print("Условия испытания")
    for key in ("machine", "python", "user", "repeats", "warmup", "app_today"):
        print(f"  {key}: {work['meta'][key]}")
    print(f"  строк (малое): {small['meta']['rows_before']}")
    print(f"  строк (рабочее): {work['meta']['rows_before']}")
    print(f"  записей выдач добавлено замером (малое / рабочее): "
          f"{small['meta']['loans_added_by_measurement']} / {work['meta']['loans_added_by_measurement']}")

    print("\nТаблица 5. Время ответа операций, мс")
    print(f"{'Операция':18} {'p50 малое':>10} {'p95 малое':>10} {'p50 рабочее':>12} "
          f"{'p95 рабочее':>12} {'max рабочее':>12} {'Рост p50':>9}")
    for op in work["operations"]:
        s = small_ops[op["name"]]
        growth = op["p50"] / s["p50"] if s["p50"] else float("nan")
        print(f"{op['name']:18} {s['p50']:10.2f} {s['p95']:10.2f} {op['p50']:12.2f} "
              f"{op['p95']:12.2f} {op['max']:12.2f} {growth:8.1f}x")

    print("\nТаблица 6. Куда уходит время операции (рабочее наполнение), мс")
    print("(«В коде» включает открытие соединения с базой, оно показано отдельным столбцом)")
    print(f"{'Операция':18} {'Время p50':>10} {'В базе':>9} {'В коде':>9} {'из них соедин.':>14} {'Запросов':>9}")
    for op in work["operations"]:
        print(f"{op['name']:18} {op['p50']:10.2f} {op['db_p50']:9.2f} {op['app_p50']:9.2f} "
              f"{op['connect_p50']:14.2f} {op['db_queries']:9.0f}")

    print("\nДля сопоставления: объём основной таблицы вырос в "
          f"{work['meta']['rows_before']['loan'] / small['meta']['rows_before']['loan']:.0f} раз.")


if __name__ == "__main__":
    main()
