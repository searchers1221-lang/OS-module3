#!/usr/bin/env python3
"""Задача B: N рабочих процессов через os.fork, результат — родителю через os.pipe.

Запуск:   python3 parallel_logs.py            (4 процесса, папка logs/)
          python3 parallel_logs.py -n 2       (2 процесса)
          python3 parallel_logs.py --check-zombies   (в конце показать, что зомби нет)

Работает только в Linux / WSL (os.fork в обычном Windows нет).
"""
import argparse
import json
import os
import signal
import subprocess
import sys
import time
import traceback

import logstats


def run(n_workers, files):
    workers = []  # список (pid, read_fd)
    try:
        for i in range(n_workers):
            chunk = files[i::n_workers]          # каждому процессу — своя часть файлов
            read_fd, write_fd = os.pipe()        # труба: ребёнок пишет в write_fd, родитель читает из read_fd
            pid = os.fork()
            if pid == 0:
                # ===== ЭТО РЕБЁНОК =====
                code = 0
                try:
                    os.close(read_fd)            # читать из своей трубы ребёнку не нужно
                    for _, fd in workers:        # и чужие трубы (унаследованные) тоже не нужны
                        os.close(fd)
                    data = json.dumps(logstats.process_files(chunk)).encode()
                    with os.fdopen(write_fd, "wb") as out:
                        out.write(data)          # закрытие out даёт родителю сигнал «конец данных»
                except BaseException:
                    traceback.print_exc()
                    code = 1
                os._exit(code)                   # именно _exit: не запускать код родителя при выходе
            # ===== ЭТО РОДИТЕЛЬ =====
            os.close(write_fd)                   # иначе read() никогда не увидит конец данных
            workers.append((pid, read_fd))

        parts = []
        for k, (pid, read_fd) in enumerate(workers):
            chunks = []
            while True:
                block = os.read(read_fd, 65536)  # ждём, пока ребёнок всё запишет и закроет трубу
                if not block:
                    break
                chunks.append(block)
            os.close(read_fd)
            data = b"".join(chunks)
            workers[k] = (pid, -1)
            _, status = os.waitpid(pid, 0)       # «хороним» ребёнка — так не остаётся зомби
            workers[k] = (-1, -1)
            if status != 0:
                raise RuntimeError(f"рабочий процесс {pid} завершился с ошибкой (status={status})")
            parts.append(json.loads(data))
        return logstats.merge(parts)
    finally:
        # если что-то пошло не так — не оставляем детей без присмотра
        for pid, fd in workers:
            if fd >= 0:
                try:
                    os.close(fd)
                except OSError:
                    pass
            if pid > 0:
                try:
                    os.kill(pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(pid, 0)
                except ChildProcessError:
                    pass


def show_zombies():
    me = os.getpid()
    out = subprocess.run(["ps", "-eo", "pid,ppid,stat,comm"], capture_output=True, text=True).stdout
    lines = out.splitlines()
    print("\n--- ps: процессы, у которых родитель — наш скрипт, и все зомби (STAT=Z) ---")
    print(lines[0])
    found = False
    for line in lines[1:]:
        f = line.split()
        if f[2].startswith("Z") or (int(f[1]) == me and f[3] != "ps"):
            print(line)
            found = True
    print("ЗОМБИ НЕТ" if not found else "ВНИМАНИЕ: найдены процессы выше")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("-n", type=int, default=4, help="число рабочих процессов")
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--quiet", action="store_true", help="не печатать отчёт (для замера времени)")
    ap.add_argument("--check-zombies", action="store_true")
    args = ap.parse_args()

    if not hasattr(os, "fork"):
        sys.exit("os.fork нет в этой системе. Запустите в WSL / Linux.")
    files = logstats.list_logs(args.logs)
    if not files:
        sys.exit(f"В папке '{args.logs}' нет файлов access_*.log")

    t0 = time.perf_counter()
    stats = run(args.n, files)
    elapsed = time.perf_counter() - t0
    if not args.quiet:
        print(logstats.format_report(stats))
    print(f"\n[N={args.n}] время: {elapsed:.2f} с", file=sys.stderr)
    if args.check_zombies:
        show_zombies()


if __name__ == "__main__":
    main()
