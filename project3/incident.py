#!/usr/bin/env python3
"""Задача C3: найти начало и конец сбоя по времени в строках журнала.

Идея. Фоновые ошибки 5xx бывают всегда (примерно одна в пару минут по всему сайту).
Сбой — это когда ошибки идут «густо». Ищем «всплески»: цепочки ошибок, где
между соседними прошло не больше N секунд, и в цепочке много ошибок.

Шаг 1. Для каждого пути отдельно (пауза до 5 минут) — ищем сбой одного пути.
Шаг 2. Эти ошибки «вычитаем» и ищем всплеск по всем путям сразу (пауза до 1 минуты) —
       так находится общий сбой всего сайта.
"""
import sys
from datetime import datetime

import logstats

MIN_ERRORS = 30          # короче этого — считаем случайностью
GAP_PATH = 300           # сек между ошибками одного пути
GAP_SITE = 60            # сек между ошибками по всему сайту


def read_logs(log_dir):
    errors = []    # (время, путь, файл, номер_строки, текст)
    requests = []  # (время, путь)
    for p in logstats.list_logs(log_dir):
        name = p.replace("\\", "/").rsplit("/", 1)[-1]
        with open(p, encoding="utf-8") as f:
            for no, line in enumerate(f, 1):
                parts = line.split()
                if len(parts) != 7:
                    continue
                ts = datetime.strptime(parts[0] + " " + parts[1], "%Y-%m-%d %H:%M:%S")
                requests.append((ts, parts[4]))
                if parts[5].startswith("5"):
                    errors.append((ts, parts[4], name, no, line.rstrip()))
    return errors, requests


def clusters(errs, gap):
    """Делит отсортированные по времени ошибки на цепочки с паузами не больше gap секунд."""
    result, cur = [], []
    for e in errs:
        if cur and (e[0] - cur[-1][0]).total_seconds() > gap:
            result.append(cur)
            cur = []
        cur.append(e)
    if cur:
        result.append(cur)
    return result


def describe(title, cl, requests, only_path=None):
    start, end = cl[0], cl[-1]
    n_req = sum(1 for t, p in requests
                if start[0] <= t <= end[0] and (only_path is None or p == only_path))
    paths = {}
    for e in cl:
        paths[e[1]] = paths.get(e[1], 0) + 1
    print(title)
    print(f"  Начало: {start[0]}  (файл {start[2]}, строка {start[3]})")
    print(f"          {start[4]}")
    print(f"  Конец:  {end[0]}  (файл {end[2]}, строка {end[3]})")
    print(f"          {end[4]}")
    print(f"  Длительность: {end[0] - start[0]}")
    what = f"запросов к {only_path}" if only_path else "запросов ко всему сайту"
    print(f"  Ошибок 5xx: {len(cl)} из {n_req} {what} ({100 * len(cl) / n_req:.1f}%)")
    print(f"  Файлы: {', '.join(sorted({e[2] for e in cl}))}")
    top = sorted(paths.items(), key=lambda kv: -kv[1])
    print("  Ошибки по путям: " + ", ".join(f"{p} — {c}" for p, c in top))


def main(log_dir="logs"):
    errors, requests = read_logs(log_dir)
    errors.sort(key=lambda e: e[0])

    # ---- Шаг 1: сбой одного пути
    by_path = {}
    for e in errors:
        by_path.setdefault(e[1], []).append(e)
    found = []
    for path, errs in by_path.items():
        for cl in clusters(errs, GAP_PATH):
            if len(cl) >= MIN_ERRORS:
                found.append((path, cl))
    found.sort(key=lambda x: -len(x[1]))
    explained = set()
    for path, cl in found:
        describe(f"СБОЙ ОДНОГО ПУТИ: {path}", cl, requests, only_path=path)
        print()
        explained.update(id(e) for e in cl)

    # ---- Шаг 2: общий сбой (по остальным ошибкам)
    rest = [e for e in errors if id(e) not in explained]
    for cl in clusters(rest, GAP_SITE):
        if len(cl) >= MIN_ERRORS:
            describe("ОБЩИЙ СБОЙ САЙТА (ошибки сразу по многим путям)", cl, requests)
            print()


if __name__ == "__main__":
    main(*sys.argv[1:])
