"""Ряд потребления ресурсов во время испытания (подраздел 2.6 методички).

Раз в секунду снимается:
  * загрузка процессора и память процесса приложения (uvicorn);
  * загрузка процессора и память базы данных (контейнер Docker или процесс postgres);
  * число соединений с базой: всех и выполняющих запрос (pg_stat_activity).

Процент процессора считается от ОДНОГО ядра, как в docker stats и top:
100 % - одно ядро занято полностью, 400 % - четыре ядра.

Отдельный запуск (во время ручной ступени, остановка Ctrl+C):
    python -m load.resources --out load/results/rows.csv
"""
import argparse
import csv
import subprocess
import threading
import time

import psutil
import psycopg

from app import config

FIELDS = ["t", "system_cpu", "app_cpu", "app_mem_mb", "db_cpu", "db_mem_mb",
          "conn_total", "conn_active"]


def _unit_to_mb(text):
    """'45.2MiB' -> 45.2; поддерживает KiB, MiB, GiB, kB, MB, GB."""
    text = text.strip()
    for unit, factor in (("GiB", 1024), ("MiB", 1), ("KiB", 1 / 1024),
                         ("GB", 1000 / 1.048576), ("MB", 1 / 1.048576), ("kB", 0.001 / 1.048576),
                         ("B", 1 / 1048576)):
        if text.endswith(unit):
            return float(text[:-len(unit)]) * factor
    return None


def find_app_processes(match="uvicorn"):
    """Процессы приложения: командная строка содержит match, плюс их дочерние (--workers)."""
    found = {}
    me = psutil.Process().pid
    for proc in psutil.process_iter(["pid", "cmdline"]):
        cmd = " ".join(proc.info["cmdline"] or [])
        if match in cmd and proc.info["pid"] != me and "load.run_steps" not in cmd \
                and "load.resources" not in cmd and "py-spy" not in cmd and "k6" not in cmd:
            found[proc.info["pid"]] = proc
            try:
                for child in proc.children(recursive=True):
                    found[child.pid] = child
            except psutil.Error:
                pass
    return list(found.values())


def find_postmaster():
    """Главный процесс postgres (родитель остальных), если база запущена не в Docker."""
    names = {"postgres", "postgres.exe"}
    candidates = []
    for proc in psutil.process_iter(["name", "ppid"]):
        if (proc.info["name"] or "").lower() in names:
            candidates.append(proc)
    pids = {p.pid for p in candidates}
    for proc in candidates:
        if proc.info["ppid"] not in pids:
            return proc
    return None


def _cpu_seconds(proc):
    """Время процессора процесса и всех уже завершившихся потомков (на Linux).
    Соединения PostgreSQL - короткие отдельные процессы, поэтому их загрузку
    по cpu_percent отдельных процессов не поймать."""
    t = proc.cpu_times()
    total = t.user + t.system
    total += getattr(t, "children_user", 0) + getattr(t, "children_system", 0)
    try:
        for child in proc.children(recursive=True):
            c = child.cpu_times()
            total += c.user + c.system
    except psutil.Error:
        pass
    return total


def detect_db_container(project_dir):
    """Идентификатор контейнера базы из `docker compose ps -q db` или None, если Docker недоступен."""
    try:
        out = subprocess.run(["docker", "compose", "ps", "-q", "db"], cwd=project_dir,
                             capture_output=True, text=True, timeout=30,
                             encoding="utf-8", errors="replace").stdout.strip()
    except Exception:
        return None
    return out.splitlines()[0] if out else None


def docker_stats(container):
    """(cpu %, память МиБ) контейнера по docker stats. Вызов занимает около секунды."""
    out = subprocess.run(
        ["docker", "stats", "--no-stream", "--format", "{{.CPUPerc}}|{{.MemUsage}}", container],
        capture_output=True, text=True, timeout=20, encoding="utf-8", errors="replace",
    ).stdout.strip()
    cpu, mem = out.split("|")
    return float(cpu.strip().rstrip("%")), _unit_to_mb(mem.split("/")[0])


class Sampler(threading.Thread):
    """Фоновый поток: накапливает строки ряда в self.rows, пока не вызван stop()."""

    def __init__(self, app_match="uvicorn", db_container=None, interval=1.0):
        super().__init__(daemon=True)
        self.app_match = app_match
        self.db_container = db_container
        self.interval = interval
        self.rows = []
        self._stop_event = threading.Event()
        self._tracked = {}   # pid -> Process: нужны, чтобы cpu_percent считался между вызовами
        self._app = []
        self._postmaster = None
        self._pm_prev = None  # (время, секунды процессора) прошлого отсчёта

    def stop(self):
        self._stop_event.set()
        self.join(timeout=30)

    @staticmethod
    def _tree_mem(root):
        """Память postmaster и его процессов; исчезнувшие по ходу процессы пропускаем."""
        total = 0
        for p in [root, *root.children(recursive=True)]:
            try:
                total += p.memory_info().rss
            except psutil.Error:
                pass
        return total / 1048576

    def _cpu_mem(self, processes):
        cpu = mem = 0.0
        for proc in processes:
            try:
                if proc.pid not in self._tracked:
                    proc.cpu_percent(None)       # первый вызов только запоминает время
                    self._tracked[proc.pid] = proc
                    continue
                cpu += proc.cpu_percent(None)
                mem += proc.memory_info().rss / 1048576
            except psutil.Error:
                self._tracked.pop(proc.pid, None)
        return cpu, mem

    def run(self):
        started = time.monotonic()
        psutil.cpu_percent(None)
        conn = None
        try:
            conn = psycopg.connect(config.DATABASE_URL, autocommit=True)
        except Exception as error:       # без соединений выборка продолжится, столбцы будут пустыми
            print(f"[resources] нет соединения с базой для pg_stat_activity: {error}")
        tick = 0
        while not self._stop_event.is_set():
            loop_start = time.monotonic()
            row = {"t": round(loop_start - started, 1), "system_cpu": psutil.cpu_percent(None)}
            if tick % 5 == 0:   # набор процессов обновляется не каждую секунду
                self._app = find_app_processes(self.app_match)
                if not self.db_container and self._postmaster is None:
                    self._postmaster = find_postmaster()
            row["app_cpu"], row["app_mem_mb"] = self._cpu_mem(self._app)
            if self.db_container:
                try:
                    row["db_cpu"], row["db_mem_mb"] = docker_stats(self.db_container)
                except Exception:
                    row["db_cpu"] = row["db_mem_mb"] = None
            elif self._postmaster is not None:
                try:
                    now, seconds = time.monotonic(), _cpu_seconds(self._postmaster)
                    row["db_cpu"] = (None if self._pm_prev is None else
                                     (seconds - self._pm_prev[1]) / (now - self._pm_prev[0]) * 100)
                    self._pm_prev = (now, seconds)
                    row["db_mem_mb"] = self._tree_mem(self._postmaster)
                except psutil.Error:
                    row["db_cpu"] = row["db_mem_mb"] = None
            else:
                row["db_cpu"] = row["db_mem_mb"] = None
            row["conn_total"] = row["conn_active"] = None
            if conn is not None:
                try:
                    total, active = conn.execute(
                        "SELECT count(*), count(*) FILTER (WHERE state = 'active') "
                        "FROM pg_stat_activity "
                        "WHERE datname = %s AND backend_type = 'client backend' "
                        "AND pid <> pg_backend_pid()", (config.PREFIX,)).fetchone()
                    row["conn_total"], row["conn_active"] = total, active
                except Exception:
                    pass
            if tick > 0:    # первый отсчёт только запоминает время: проценты в нём нулевые
                self.rows.append({k: (round(v, 1) if isinstance(v, float) else v)
                                  for k, v in row.items()})
            tick += 1
            self._stop_event.wait(max(self.interval - (time.monotonic() - loop_start), 0))
        if conn is not None:
            conn.close()


def write_csv(rows, path):
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=FIELDS)
        writer.writeheader()
        writer.writerows(rows)


def summarize(rows):
    """Медиана и максимум по столбцам ряда (пустые значения пропускаются)."""
    out = {}
    for field in FIELDS[1:]:
        values = sorted(r[field] for r in rows if r.get(field) is not None)
        if values:
            out[field] = {"median": values[len(values) // 2], "max": values[-1]}
    return out


def main():
    parser = argparse.ArgumentParser(description="Ряд потребления ресурсов, остановка Ctrl+C")
    parser.add_argument("--out", default="resources.csv")
    parser.add_argument("--app-match", default="uvicorn")
    parser.add_argument("--db-container", default=None, help="имя контейнера базы (docker stats)")
    args = parser.parse_args()
    sampler = Sampler(args.app_match, args.db_container)
    sampler.start()
    print("Снимаю ряд раз в секунду, остановка: Ctrl+C")
    try:
        while True:
            time.sleep(1)
            if sampler.rows:
                last = sampler.rows[-1]
                print(" ".join(f"{k}={last[k]}" for k in FIELDS))
    except KeyboardInterrupt:
        sampler.stop()
        write_csv(sampler.rows, args.out)
        print(f"Сохранено: {args.out}")


if __name__ == "__main__":
    main()
