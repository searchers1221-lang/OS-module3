#!/usr/bin/env bash
# errors.sh — задача A1.
# Для каждого файла журнала печатает число строк и число ответов 5xx,
# в конце — итог и файл с наибольшим числом 5xx.
#
# Запуск:  ./errors.sh            (журналы берутся из папки logs/)
#          ./errors.sh other_dir  (или из другой папки)

set -euo pipefail

LOG_DIR="${1:-logs}"

if [ ! -d "$LOG_DIR" ]; then
    echo "Ошибка: папка '$LOG_DIR' не найдена" >&2
    exit 1
fi

total_lines=0
total_5xx=0
max_5xx=-1
max_file=""
files_found=0

printf '%-16s %8s %8s\n' "ФАЙЛ" "СТРОК" "5xx"

for file in "$LOG_DIR"/access_*.log; do
    [ -e "$file" ] || continue          # если файлов нет, шаблон остаётся текстом
    files_found=$((files_found + 1))

    lines=$(wc -l < "$file")
    # 6-е поле строки — код ответа; считаем те, что >= 500
    errors=$(awk '$6 >= 500 { n++ } END { print n + 0 }' "$file")

    printf '%-16s %8d %8d\n' "$(basename "$file")" "$lines" "$errors"

    total_lines=$((total_lines + lines))
    total_5xx=$((total_5xx + errors))
    if [ "$errors" -gt "$max_5xx" ]; then
        max_5xx=$errors
        max_file=$(basename "$file")
    fi
done

if [ "$files_found" -eq 0 ]; then
    echo "Ошибка: в '$LOG_DIR' нет файлов access_*.log" >&2
    exit 1
fi

echo "----------------------------------------"
echo "Файлов:               $files_found"
echo "Всего строк:          $total_lines"
echo "Всего ответов 5xx:    $total_5xx"
echo "Больше всего 5xx:     $max_file ($max_5xx)"
