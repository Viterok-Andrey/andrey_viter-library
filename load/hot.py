"""Горячие функции из файла свёрнутых стеков py-spy.

    python -m load.hot load/results/profile/profile.raw

Для каждой функции считаются две доли от всех снятых стеков:
  self  - стек закончился в самой функции (время тратится в её собственных строках);
  total - функция есть где-то в стеке (время в ней и во всём, что она вызвала).
Показаны функции проекта и сторонние библиотеки (psycopg, starlette и т. д.) отдельно.
"""
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

FRAME = re.compile(r"^(?P<func>.+?) \((?P<file>.+?):(?P<line>\d+)\)$")


def parse(raw_path):
    """Возвращает (всего стеков, self, total, строки), ключ - (функция, файл)."""
    total_samples = 0
    self_cnt, total_cnt = Counter(), Counter()
    lines = defaultdict(Counter)
    for text in Path(raw_path).read_text(encoding="utf-8", errors="replace").splitlines():
        text = text.strip()
        if not text or " " not in text:
            continue
        stack, _, count = text.rpartition(" ")
        if not count.isdigit():
            continue
        count = int(count)
        keys = []
        for part in stack.split(";"):
            m = FRAME.match(part.strip())
            if m:
                key = (m["func"], m["file"].replace("\\", "/"))
                keys.append(key)
                lines[key][int(m["line"])] += count
        if not keys:
            continue
        total_samples += count
        self_cnt[keys[-1]] += count
        for key in set(keys):
            total_cnt[key] += count
    return total_samples, self_cnt, total_cnt, lines


def is_project(file, root):
    """py-spy пишет пути проекта относительными (app/main.py) или полными - принимаем оба вида."""
    f = file.replace("\\", "/")
    if "site-packages" in f or "/venv/" in f or "/.venv/" in f or "/lib/python" in f.lower():
        return False
    r = str(root).replace("\\", "/").rstrip("/") + "/"
    return f.startswith(r) or f.startswith(("app/", "scripts/", "seed"))


def short(file, root):
    f = file.replace("\\", "/")
    r = str(root).replace("\\", "/").rstrip("/") + "/"
    if f.startswith(r):
        return f[len(r):]
    idx = f.find("site-packages/")
    return f[idx + len("site-packages/"):] if idx >= 0 else f


def table(title, keys, counters, total, lines, root, top):
    self_cnt, total_cnt = counters
    out = [f"### {title}", "", "| Функция | Файл:строка | self, % | total, % |", "|---|---|---:|---:|"]
    for key in keys[:top]:
        func, file = key
        line = lines[key].most_common(1)[0][0]
        out.append(f"| `{func}` | {short(file, root)}:{line} | "
                   f"{self_cnt[key] / total * 100:.1f} | {total_cnt[key] / total * 100:.1f} |")
    return out


def report(raw_path, root, out_path=None, top=15):
    total, self_cnt, total_cnt, lines = parse(raw_path)
    if total == 0:
        print("В профиле нет стеков: нагрузка не дошла до процесса или всё время ушло в ожидание (попробуйте --idle)")
        return
    proj = [k for k in total_cnt if is_project(k[1], root)]
    proj.sort(key=lambda k: total_cnt[k], reverse=True)
    leaves = sorted(self_cnt, key=lambda k: self_cnt[k], reverse=True)
    result = [f"Снято стеков: {total}", ""]
    result += table("Функции проекта по доле «total» (есть в стеке)", proj, (self_cnt, total_cnt),
                    total, lines, root, top)
    result += [""] + table("Где стек заканчивается («self»), все модули", leaves, (self_cnt, total_cnt),
                           total, lines, root, top)
    text = "\n".join(result)
    print(text)
    if out_path:
        Path(out_path).write_text(text + "\n", encoding="utf-8")
        print(f"\nТаблица сохранена: {out_path}")


if __name__ == "__main__":
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    report(sys.argv[1], Path(__file__).resolve().parent.parent, None, top=15)
