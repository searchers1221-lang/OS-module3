#!/usr/bin/env python3
"""Задача C: три способа вернуть результат родителю + корректная остановка по Ctrl+C.

Способы:
  pipe — ребёнок пишет результат в os.pipe
  shm  — ребёнок пишет в общую память multiprocessing.shared_memory
  tmp  — ребёнок пишет результат во временный файл

Запуск:  python3 advanced.py --method pipe -n 4
         python3 advanced.py --method shm  -n 4 --quiet
         python3 advanced.py --method tmp  -n 4 --delay 0.5   (медленно — чтобы успеть нажать Ctrl+C)

Работает только в Linux / WSL.
"""
import argparse
import json
import os
import shutil
import signal
import struct
import sys
import tempfile
import time
import traceback
from multiprocessing import shared_memory

import logstats

SLOT = 256 * 1024  # место под результат одного процесса в общей памяти


def _to_keyboard_interrupt(signum, frame):
    raise KeyboardInterrupt


def child_main(method, idx, chunk, delay, write_fd, shm, tmpdir):
    """Тело рабочего процесса. Ничего не возвращает — результат отдаёт выбранным способом."""
    signal.signal(signal.SIGINT, signal.SIG_DFL)    # по Ctrl+C ребёнок просто умирает
    signal.signal(signal.SIGTERM, signal.SIG_DFL)   # и по SIGTERM от родителя — тоже
    data = json.dumps(logstats.process_files(chunk, delay)).encode()
    if method == "pipe":
        with os.fdopen(write_fd, "wb") as out:
            out.write(data)
    elif method == "shm":
        if len(data) + 4 > SLOT:
            raise RuntimeError("результат не помещается в слот общей памяти")
        off = idx * SLOT
        shm.buf[off + 4: off + 4 + len(data)] = data
        struct.pack_into("<I", shm.buf, off, len(data))   # длину пишем последней
    elif method == "tmp":
        tmp = os.path.join(tmpdir, f"part{idx}.tmp")
        with open(tmp, "wb") as f:
            f.write(data)
        os.replace(tmp, os.path.join(tmpdir, f"part{idx}.json"))  # файл появляется сразу целиком


def run(method, n_workers, files, delay):
    shm = None
    tmpdir = None
    workers = []   # [pid, read_fd]; pid=-1 — уже «похоронен», fd=-1 — уже закрыт
    if method == "shm":
        shm = shared_memory.SharedMemory(create=True, size=n_workers * SLOT)
    elif method == "tmp":
        tmpdir = tempfile.mkdtemp(prefix="logs_")
    try:
        for i in range(n_workers):
            chunk = files[i::n_workers]
            read_fd = write_fd = -1
            if method == "pipe":
                read_fd, write_fd = os.pipe()
            pid = os.fork()
            if pid == 0:
                code = 0
                try:
                    if read_fd >= 0:
                        os.close(read_fd)
                    for _, fd in workers:
                        if fd >= 0:
                            os.close(fd)
                    child_main(method, i, chunk, delay, write_fd, shm, tmpdir)
                except BaseException:
                    traceback.print_exc()
                    code = 1
                os._exit(code)
            if write_fd >= 0:
                os.close(write_fd)
            workers.append([pid, read_fd])

        parts = []
        for k, w in enumerate(workers):
            pid, read_fd = w
            raw = None
            if method == "pipe":
                chunks = []
                while True:
                    block = os.read(read_fd, 65536)   # читаем, пока ребёнок не закроет трубу
                    if not block:
                        break
                    chunks.append(block)
                os.close(read_fd)
                w[1] = -1                             # помечаем: труба уже закрыта
                raw = b"".join(chunks)
            _, status = os.waitpid(pid, 0)
            w[0] = -1
            if status != 0:
                raise RuntimeError(f"рабочий процесс {pid} завершился с ошибкой (status={status})")
            if method == "shm":
                off = k * SLOT
                (ln,) = struct.unpack_from("<I", shm.buf, off)
                raw = bytes(shm.buf[off + 4: off + 4 + ln])
            elif method == "tmp":
                with open(os.path.join(tmpdir, f"part{k}.json"), "rb") as f:
                    raw = f.read()
            parts.append(json.loads(raw))
        return logstats.merge(parts)
    finally:
        # Выполняется ВСЕГДА: и при успехе, и при Ctrl+C, и при ошибке.
        for w in workers:
            if w[0] > 0:
                try:
                    os.kill(w[0], signal.SIGTERM)      # просим живых детей завершиться
                except ProcessLookupError:
                    pass
                try:
                    os.waitpid(w[0], 0)                # и обязательно «хороним» — нет зомби
                except ChildProcessError:
                    pass
            if w[1] >= 0:
                try:
                    os.close(w[1])
                except OSError:
                    pass
        if shm is not None:
            try:
                shm.close()
            except BufferError:
                pass
            shm.unlink()                               # удаляем сегмент из /dev/shm
            # Python сам запускает служебный процесс resource_tracker для shared_memory.
            # Останавливаем его и «хороним», чтобы после нас не осталось сирот и зомби.
            try:
                from multiprocessing import resource_tracker
                resource_tracker._resource_tracker._stop()
            except Exception:
                pass
        if tmpdir is not None:
            shutil.rmtree(tmpdir, ignore_errors=True)  # удаляем временные файлы


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--method", choices=["pipe", "shm", "tmp"], default="pipe")
    ap.add_argument("-n", type=int, default=4)
    ap.add_argument("--logs", default="logs")
    ap.add_argument("--delay", type=float, default=0.0, help="пауза после каждого файла (для проверки Ctrl+C)")
    ap.add_argument("--quiet", action="store_true")
    args = ap.parse_args()

    if not hasattr(os, "fork"):
        sys.exit("os.fork нет в этой системе. Запустите в WSL / Linux.")
    files = logstats.list_logs(args.logs)
    if not files:
        sys.exit(f"В папке '{args.logs}' нет файлов access_*.log")

    signal.signal(signal.SIGTERM, _to_keyboard_interrupt)   # kill <pid> ведёт себя как Ctrl+C
    t0 = time.perf_counter()
    try:
        stats = run(args.method, args.n, files, args.delay)
    except KeyboardInterrupt:
        print("\nПрервано (Ctrl+C). Процессы завершены, память и временные файлы очищены.", file=sys.stderr)
        sys.exit(130)
    elapsed = time.perf_counter() - t0
    if not args.quiet:
        print(logstats.format_report(stats))
    print(f"[метод={args.method} N={args.n}] время: {elapsed:.2f} с", file=sys.stderr)


if __name__ == "__main__":
    main()
