"""Общие функции разбора журналов (используют parallel_logs.py и advanced.py)."""
import glob
import os
import time


def list_logs(log_dir):
    return sorted(glob.glob(os.path.join(log_dir, "access_*.log")))


def process_files(paths, delay=0.0):
    """Читает файлы, возвращает {имя_файла: {путь: [запросов, ответов_5xx]}}.

    delay — искусственная пауза после каждого файла (нужна только чтобы
    успеть нажать Ctrl+C при проверке задания C2).
    """
    stats = {}
    for p in paths:
        per_path = {}
        with open(p, encoding="utf-8", errors="replace") as f:
            for line in f:
                # дата время IP метод путь код длительность
                parts = line.split()
                if len(parts) != 7:
                    continue
                rec = per_path.setdefault(parts[4], [0, 0])
                rec[0] += 1
                if parts[5].startswith("5"):
                    rec[1] += 1
        stats[os.path.basename(p)] = per_path
        if delay:
            time.sleep(delay)
    return stats


def merge(parts):
    """Склеивает результаты рабочих процессов (файлы у них не пересекаются)."""
    merged = {}
    for part in parts:
        merged.update(part)
    return merged


def _pct(part, whole):
    return 100.0 * part / whole if whole else 0.0


def format_report(stats):
    total = err = 0
    by_path, by_file, pairs = {}, {}, []
    for fname, paths in stats.items():
        for path, (t, e) in paths.items():
            total += t
            err += e
            by_path.setdefault(path, [0, 0])
            by_path[path][0] += t
            by_path[path][1] += e
            by_file.setdefault(fname, [0, 0])
            by_file[fname][0] += t
            by_file[fname][1] += e
            pairs.append((fname, path, t, e))

    out = []
    out.append(f"ИТОГО: запросов {total}, ответов 5xx {err} ({_pct(err, total):.3f}%)")
    out.append("")
    out.append("ДОЛЯ 5xx ПО ПУТЯМ (от большей к меньшей)")
    out.append(f"{'путь':<18}{'запросов':>10}{'5xx':>8}{'доля':>9}")
    for path, (t, e) in sorted(by_path.items(), key=lambda kv: -_pct(kv[1][1], kv[1][0])):
        out.append(f"{path:<18}{t:>10}{e:>8}{_pct(e, t):>8.2f}%")
    out.append("")
    out.append("ДОЛЯ 5xx ПО ФАЙЛАМ")
    out.append(f"{'файл':<16}{'запросов':>10}{'5xx':>8}{'доля':>9}")
    for fname in sorted(by_file):
        t, e = by_file[fname]
        out.append(f"{fname:<16}{t:>10}{e:>8}{_pct(e, t):>8.2f}%")
    out.append("")
    out.append("СБОЙ: пары (файл, путь) с наибольшей долей 5xx (не меньше 30 запросов)")
    out.append(f"{'файл':<16}{'путь':<18}{'запросов':>10}{'5xx':>6}{'доля':>9}")
    top = sorted((p for p in pairs if p[2] >= 30), key=lambda p: -_pct(p[3], p[2]))[:5]
    for fname, path, t, e in top:
        out.append(f"{fname:<16}{path:<18}{t:>10}{e:>6}{_pct(e, t):>8.1f}%")
    if top:
        fname, path, t, e = top[0]
        out.append("")
        out.append(f"=> Сбой: путь {path} в файле {fname} ({e} ошибок 5xx из {t} запросов)")
    return "\n".join(out)
