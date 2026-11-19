"""Графики по результатам ступенчатого испытания.

    python -m load.plot mixed
    python -m load.plot heavy

Рисует в load/results/<сценарий>/:
  p95_vs_rate.png   p95 по ступеням, линия порога, отмечены допустимая интенсивность и излом
  resources_<N>.png ресурсы на ступени N (по умолчанию - на ступени излома и допустимой)
"""
import argparse
import csv
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

LOAD = Path(__file__).resolve().parent


def load_steps(scenario):
    path = LOAD / "results" / scenario / "steps.json"
    if not path.exists():
        sys.exit(f"Нет {path}: сначала запустите python -m load.run_steps {scenario}")
    return json.loads(path.read_text(encoding="utf-8"))


def plot_p95(scenario, data):
    steps = data["steps"]
    rates = [s["rate"] for s in steps]
    p95 = [s["p95"] for s in steps]
    fig, ax = plt.subplots(figsize=(8, 4.5), dpi=150)
    ax.plot(rates, p95, marker="o", color="#2563eb", label="p95")
    ax.axhline(data["limit_ms"], color="#dc2626", linestyle="--", label=f"порог {data['limit_ms']} мс")
    good = [s for s in steps if s["passed"]]
    bad = [s for s in steps if not s["passed"]]
    if good:
        g = good[-1]
        ax.scatter([g["rate"]], [g["p95"]], s=140, facecolors="none", edgecolors="#16a34a",
                   linewidths=2, zorder=5, label=f"допустимая: {g['rate']:g} запр/с")
    if bad:
        b = bad[0]
        ax.scatter([b["rate"]], [b["p95"]], s=140, facecolors="none", edgecolors="#dc2626",
                   linewidths=2, zorder=5, label=f"излом: {b['rate']:g} запр/с")
    ax.set_xscale("log", base=2)
    ax.set_yscale("log")
    ax.set_xticks(rates)
    ax.set_xticklabels([f"{r:g}" for r in rates])
    ax.set_xlabel("заданная интенсивность, запросов/с")
    ax.set_ylabel("p95 времени ответа, мс (лог. шкала)")
    ax.set_title("Время ответа p95 по ступеням нагрузки")
    ax.grid(True, which="both", alpha=0.3)
    ax.legend()
    fig.tight_layout()
    path = LOAD / "results" / scenario / "p95_vs_rate.png"
    fig.savefig(path)
    plt.close(fig)
    print("Сохранено:", path)


def read_csv(path):
    rows = list(csv.DictReader(open(path, encoding="utf-8")))
    def col(name):
        return [float(r[name]) if r.get(name) not in (None, "") else float("nan") for r in rows]
    return col


def plot_resources(scenario, rate):
    base = LOAD / "results" / scenario / f"rate_{rate:g}_resources.csv"
    if not base.exists():
        print("Нет файла", base)
        return
    col = read_csv(base)
    t = col("t")
    fig, axes = plt.subplots(3, 1, figsize=(8, 7.5), dpi=150, sharex=True)
    axes[0].plot(t, col("system_cpu"), label="вся машина (100 % = все ядра)", color="#6b7280")
    axes[0].set_ylabel("CPU машины, %")
    axes[1].plot(t, col("app_cpu"), label="приложение (uvicorn)", color="#2563eb")
    axes[1].plot(t, col("db_cpu"), label="база данных", color="#ea580c")
    axes[1].set_ylabel("CPU, % одного ядра")
    axes[2].plot(t, col("conn_total"), label="всего соединений", color="#7c3aed")
    axes[2].plot(t, col("conn_active"), label="активных", color="#16a34a")
    axes[2].set_ylabel("соединения с БД")
    axes[2].set_xlabel("время ступени, с")
    for ax in axes:
        ax.grid(True, alpha=0.3)
        ax.legend(loc="best")
    axes[0].set_title(f"Ресурсы на ступени {rate:g} запр/с")
    fig.tight_layout()
    path = LOAD / "results" / scenario / f"resources_{rate:g}.png"
    fig.savefig(path)
    plt.close(fig)
    print("Сохранено:", path)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", choices=["mixed", "heavy"])
    parser.add_argument("--rates", help="ступени для графика ресурсов, через запятую")
    args = parser.parse_args()
    data = load_steps(args.scenario)
    plot_p95(args.scenario, data)
    if args.rates:
        rates = [float(x) for x in args.rates.split(",")]
    else:
        steps = data["steps"]
        good = [s["rate"] for s in steps if s["passed"]]
        bad = [s["rate"] for s in steps if not s["passed"]]
        rates = ([good[-1]] if good else []) + ([bad[0]] if bad else [])
    for r in rates:
        plot_resources(args.scenario, r)


if __name__ == "__main__":
    main()
