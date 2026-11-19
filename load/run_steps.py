"""Ступенчатое испытание: одна команда прогоняет весь ряд ступеней (подразделы 2.4 и 2.5).

    python -m load.run_steps mixed      # смешанный профиль, ступени 2, 4, 8, ... запросов/с
    python -m load.run_steps heavy      # самая тяжёлая операция, ступени 1, 2, 4, ...

Перед каждой ступенью:
  1. база наполняется заново (python seed.py work): операции записи добавляют данные;
  2. скрипт ждёт, пока загрузка процессора вернётся к простою;
  3. запускается k6 и параллельно снимается ряд ресурсов раз в секунду.
Серия останавливается на первой ступени, не выдержавшей порог (p95 >= 500 мс
или ошибок >= 1 %): это точка излома, предыдущая ступень - допустимая интенсивность.

Результаты - в load/results/<сценарий>/:
  rate_<N>.txt             полный вывод k6 (для снимка в отчёт)
  rate_<N>.json            итоговые числа k6
  rate_<N>_resources.csv   ряд ресурсов этой ступени
  steps.json, steps.md     таблица ступеней
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from pathlib import Path

import psutil

from load import resources

ROOT = Path(__file__).resolve().parent.parent
LOAD = Path(__file__).resolve().parent
SCRIPTS = {"mixed": "tests/mixed.test.js", "heavy": "tests/heavy.test.js"}


def out(text=""):
    print(text, flush=True)


def wait_for_idle(threshold, consecutive=5, timeout=180):
    """Ждёт, пока загрузка процессора всей машины ниже threshold % consecutive секунд подряд."""
    psutil.cpu_percent(None)
    calm = 0
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        load = psutil.cpu_percent(interval=1)
        calm = calm + 1 if load < threshold else 0
        if calm >= consecutive:
            return True
    return False


def reseed(python):
    out("Наполнение базы заново: seed.py work")
    result = subprocess.run([python, "seed.py", "work"], cwd=ROOT, capture_output=True,
                            text=True, encoding="utf-8", errors="replace")
    if result.returncode != 0:
        sys.exit(f"seed.py завершился с ошибкой:\n{result.stdout}\n{result.stderr}")
    out("  " + result.stdout.strip().splitlines()[-1])


def read_summary(path):
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    metrics = data["metrics"]
    duration = metrics["http_req_duration{kind:load}"]
    failed = metrics["http_req_failed{kind:load}"]
    breakdown = {}
    for name, value in metrics.items():
        if name.startswith("http_req_duration{operation:"):
            op = name[len("http_req_duration{operation:"):-1]
            if op not in ("login", "setup") and value["max"] > 0:
                breakdown[op] = {"med": value["med"], "p95": value["p(95)"], "max": value["max"]}
    return {
        "median": duration["med"],
        "p95": duration["p(95)"],
        "max": duration["max"],
        "error_pct": failed["value"] * 100,
        "requests": failed["passes"] + failed["fails"],
        "dropped": int(metrics.get("dropped_iterations", {}).get("count", 0)),
        "actual_rate": metrics["iterations"]["rate"],
        "checks_pct": metrics.get("checks", {}).get("value", 1) * 100,
        "operations": breakdown,
    }


def run_step(args, scenario, rate, folder):
    name = f"rate_{rate:g}"
    summary_path = folder / f"{name}.json"
    command = [
        args.k6, "run", "--quiet",
        "-e", f"RATE={rate:g}", "-e", f"DURATION={args.duration}s",
        "-e", f"LIMIT_MS={args.limit_ms}", "-e", f"BASE={args.base}",
        "--summary-export", str(summary_path),
        str(LOAD / SCRIPTS[scenario]),
    ]
    if args.heavy:
        command[2:2] = ["-e", f"HEAVY={args.heavy}"]
    out(f"\n=== ступень {rate:g} запросов/с, {args.duration} с ({scenario}) ===")
    out("k6 " + " ".join(command[1:]))

    sampler = resources.Sampler(args.app_match, args.db_container)
    sampler.start()
    lines = []
    process = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                               text=True, encoding="utf-8", errors="replace")
    for line in process.stdout:
        lines.append(line)
        out(line.rstrip("\n"))
    code = process.wait()
    sampler.stop()

    (folder / f"{name}.txt").write_text("".join(lines), encoding="utf-8")
    resources.write_csv(sampler.rows, folder / f"{name}_resources.csv")
    if code not in (0, 99):
        sys.exit(f"k6 завершился с кодом {code}: проверьте вывод выше")

    row = {"rate": rate, "k6_exit_code": code, **read_summary(summary_path),
           "resources": resources.summarize(sampler.rows)}
    row["passed"] = row["p95"] < args.limit_ms and row["error_pct"] < 1.0
    return row


def print_resources(row):
    res = row["resources"]
    parts = []
    for key, label in (("app_cpu", "CPU приложения, %"), ("db_cpu", "CPU базы, %"),
                       ("conn_active", "активных соединений"), ("conn_total", "всех соединений")):
        if key in res:
            parts.append(f"{label}: медиана {res[key]['median']}, максимум {res[key]['max']}")
    out("  ресурсы: " + "; ".join(parts))


def table_markdown(rows, limit_ms):
    head = ("| Частота, запросов/с | Медиана, мс | p95, мс | Максимум, мс | Ошибки, % | "
            "dropped_iterations | Фактическая частота, запросов/с | Порог (p95 < "
            f"{limit_ms} мс, ошибок < 1 %) |\n|---|---|---|---|---|---|---|---|\n")
    body = ""
    for r in rows:
        body += (f"| {r['rate']:g} | {r['median']:.1f} | {r['p95']:.1f} | {r['max']:.1f} | "
                 f"{r['error_pct']:.2f} | {r['dropped']} | {r['actual_rate']:.2f} | "
                 f"{'выдержан' if r['passed'] else 'НАРУШЕН'} |\n")
    return head + body


def main():
    parser = argparse.ArgumentParser(description="Ступенчатое испытание сервиса")
    parser.add_argument("scenario", choices=SCRIPTS)
    parser.add_argument("--start", type=float, default=None,
                        help="первая ступень, запросов/с (mixed: 2, heavy: 1)")
    parser.add_argument("--factor", type=float, default=2.0, help="во сколько раз растёт частота")
    parser.add_argument("--rates", default=None,
                        help="явный список ступеней через запятую, например 1,2,4,8")
    parser.add_argument("--max-rate", type=float, default=1024)
    parser.add_argument("--duration", type=int, default=30, help="длительность ступени, с")
    parser.add_argument("--limit-ms", type=int, default=500)
    parser.add_argument("--extra-steps", type=int, default=0,
                        help="сколько ступеней выполнить после первой невыдержанной")
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--heavy", default=None, help="операция одиночного сценария")
    parser.add_argument("--idle-cpu", type=float, default=15.0,
                        help="порог простоя: загрузка процессора машины, %%")
    parser.add_argument("--no-reseed", action="store_true", help="не наполнять базу перед ступенью")
    parser.add_argument("--k6", default=shutil.which("k6") or "k6")
    parser.add_argument("--app-match", default="uvicorn", help="что искать в командной строке сервиса")
    parser.add_argument("--db-container", default=None,
                        help="контейнер базы для docker stats; по умолчанию берётся из docker compose ps")
    parser.add_argument("--no-docker", action="store_true",
                        help="не искать контейнер: база запущена без Docker")
    args = parser.parse_args()

    if args.rates:
        rates = [float(x) for x in args.rates.split(",")]
    else:
        start = args.start or (2.0 if args.scenario == "mixed" else 1.0)
        rates, rate = [], start
        while rate <= args.max_rate:
            rates.append(rate)
            rate *= args.factor
    folder = LOAD / "results" / args.scenario
    folder.mkdir(parents=True, exist_ok=True)

    if args.db_container is None and not args.no_docker:
        args.db_container = resources.detect_db_container(ROOT)
    out("База данных: " + (f"контейнер {args.db_container[:12]} (docker stats)" if args.db_container
        else "процесс postgres на этой машине (Docker не найден)"))
    apps = resources.find_app_processes(args.app_match)
    out("Процессы приложения: " + (", ".join(str(p.pid) for p in apps) or
        "НЕ НАЙДЕНЫ (запущен ли uvicorn? столбцы app_* будут пустыми)"))
    out(f"Условия: ядер {os.cpu_count()}, k6 {args.k6}, адрес {args.base}")

    rows, failed_at, extra = [], None, 0
    for rate in rates:
        if not args.no_reseed:
            reseed(sys.executable)
        if wait_for_idle(args.idle_cpu):
            out("Загрузка процессора вернулась к простою")
        else:
            out(f"ВНИМАНИЕ: загрузка не упала ниже {args.idle_cpu} % за 180 с, "
                "закройте лишние программы; ступень снята при фоновой нагрузке")
        row = run_step(args, args.scenario, rate, folder)
        rows.append(row)
        out(f"  итог ступени: медиана {row['median']:.1f} мс, p95 {row['p95']:.1f} мс, "
            f"ошибок {row['error_pct']:.2f} %, dropped {row['dropped']}, "
            f"фактическая частота {row['actual_rate']:.2f} -> "
            f"{'порог выдержан' if row['passed'] else 'ПОРОГ НАРУШЕН'}")
        print_resources(row)
        (folder / "steps.json").write_text(
            json.dumps({"scenario": args.scenario, "limit_ms": args.limit_ms, "steps": rows},
                       ensure_ascii=False, indent=2), encoding="utf-8")
        if not row["passed"]:
            failed_at = failed_at or rate
            if extra >= args.extra_steps:
                break
            extra += 1
        if row["checks_pct"] < 99:
            out(f"  ВНИМАНИЕ: пройдено проверок {row['checks_pct']:.1f} %: часть ответов неверна по содержанию")

    table = table_markdown(rows, args.limit_ms)
    (folder / "steps.md").write_text(table, encoding="utf-8")
    out("\n" + table)
    if failed_at is None:
        out("Порог выдержан на всех ступенях: увеличьте --max-rate или --start и повторите.")
    else:
        before = [r["rate"] for r in rows if r["rate"] < failed_at and r["passed"]]
        out(f"Точка излома: {failed_at:g} запросов/с.")
        if before:
            out(f"Допустимая интенсивность: {max(before):g} запросов/с.")
        else:
            out("Первая же ступень не выдержала порог: точки излома нет, операция медленна сама по себе.\n"
                "Укажите предел пропускной способности: частоту, после которой фактическая частота "
                "перестаёт расти (запустите с --rates 0.5,1,2,4 и сравните столбец «Фактическая частота»).")


if __name__ == "__main__":
    main()
