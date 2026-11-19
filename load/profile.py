"""Профиль сервиса под нагрузкой (подраздел 2.6): py-spy во время испытания самой тяжёлой операции.

    python -m load.profile --rate 4 --duration 30

Что делает:
  1. запускает k6 (load/tests/heavy.test.js) на заданной интенсивности;
  2. через 5 секунд подключает к процессу uvicorn py-spy и записывает профиль:
       load/results/profile/flamegraph.svg   - флеймграф (открыть в браузере)
       load/results/profile/profile.raw      - свёрнутые стеки для разбора
  3. разбирает горячие функции (load.hot) и печатает таблицу.

Запускайте на интенсивности предела тяжёлой операции (ступень излома или чуть ниже):
под нулевой нагрузкой профиль пустой. По умолчанию py-spy видит только работающий код;
ключ --idle добавляет ожидания (ответ базы, сокеты) - тогда ждущие потоки тоже попадут в профиль.
Профиль записывается минимум 10 секунд.
"""
import argparse
import shutil
import subprocess
import sys
import time
from pathlib import Path

from load import hot, resources

ROOT = Path(__file__).resolve().parent.parent
LOAD = Path(__file__).resolve().parent


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--rate", type=float, required=True, help="запросов/с для тяжёлой операции")
    parser.add_argument("--duration", type=int, default=30, help="длительность k6, с (по умолчанию 30)")
    parser.add_argument("--heavy", default=None, help="операция (по умолчанию из config.js)")
    parser.add_argument("--base", default="http://localhost:8080")
    parser.add_argument("--k6", default="k6")
    parser.add_argument("--py-spy", default="py-spy", dest="pyspy")
    parser.add_argument("--app-match", default="uvicorn")
    parser.add_argument("--idle", action="store_true", help="включать ожидающие потоки (py-spy --idle)")
    parser.add_argument("--hz", type=int, default=100, help="частота снятия стеков (по умолчанию 100)")
    parser.add_argument("--out", default=str(LOAD / "results" / "profile"))
    args = parser.parse_args()

    if args.duration < 15:
        sys.exit("Нужно --duration не меньше 15: профиль пишется минимум 10 секунд")
    for tool in (args.k6, args.pyspy):
        if shutil.which(tool) is None:
            sys.exit(f"Не найден {tool}: установите (для py-spy: pip install py-spy)")
    apps = resources.find_app_processes(args.app_match)
    if not apps:
        sys.exit("Процесс uvicorn не найден: сначала запустите сервис")
    main_proc = min(apps, key=lambda p: p.pid)   # родитель: py-spy возьмёт и дочерние (--subprocesses)
    print(f"Профилируем процесс {main_proc.pid} (uvicorn), всего процессов приложения: {len(apps)}")

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    record_seconds = args.duration - 8
    k6_cmd = [args.k6, "run", "--quiet", "-e", f"RATE={args.rate:g}", "-e", f"DURATION={args.duration}s",
              "-e", f"BASE={args.base}", str(LOAD / "tests" / "heavy.test.js")]
    if args.heavy:
        k6_cmd[2:2] = ["-e", f"HEAVY={args.heavy}"]
    common = [args.pyspy, "record", "--pid", str(main_proc.pid), "--duration", str(record_seconds),
              "--rate", str(args.hz), "--subprocesses"]
    if args.idle:
        common.append("--idle")
    raw_path, svg_path = out_dir / "profile.raw", out_dir / "flamegraph.svg"

    print("k6:", " ".join(k6_cmd[1:]))
    k6 = subprocess.Popen(k6_cmd, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                          text=True, encoding="utf-8", errors="replace")
    time.sleep(5 + 4)   # setup() k6 (логин, выборка id) + прогрев
    spies = [subprocess.Popen(common + ["--format", "raw", "--output", str(raw_path)]),
             subprocess.Popen(common + ["--format", "flamegraph", "--output", str(svg_path)])]
    for line in k6.stdout:
        print(line.rstrip("\n"))
    k6.wait()
    for spy in spies:
        spy.wait()
    (out_dir / "k6.txt").write_text("", encoding="utf-8")

    if not raw_path.exists():
        sys.exit("py-spy не создал профиль. На Linux нужен запуск с sudo или ptrace_scope=0")
    print(f"\nФлеймграф: {svg_path}\nСтеки:     {raw_path}\n")
    hot.report(raw_path, ROOT, out_dir / "hot.md", top=15)


if __name__ == "__main__":
    main()
