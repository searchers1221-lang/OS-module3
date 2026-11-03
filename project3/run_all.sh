#!/usr/bin/env bash
# run_all.sh — запускает ВСЕ задания проекта по порядку и складывает вывод в папку results/.
# Запуск (в WSL / Linux, из папки проекта):   bash run_all.sh

cd "$(dirname "$0")" || exit 1
mkdir -p results
TIMEFORMAT='%R сек'

have_strace=1
command -v strace >/dev/null 2>&1 || have_strace=0
LOG1="logs/access_01.log"

# timeit МЕТКА команда... — печатает «МЕТКА: время»
timeit() {
    local label=$1; shift
    { time "$@" >/dev/null 2>&1; } 2>&1 | sed "s/^/$label: /"
}

# top3 ФАЙЛ — три самых частых системных вызова из вывода strace -c
top3() {
    awk '$1 ~ /^[0-9.]+$/ && $NF != "total" { print "  " $4 " вызовов  " $NF }' "$1" | head -3
}

echo "=== A1: errors.sh ==="
bash errors.sh > results/A1_errors_output.txt && tail -5 results/A1_errors_output.txt

echo
echo "=== A2: strace -c для wc -l и для Python-подсчёта (файл $LOG1) ==="
if [ "$have_strace" -eq 1 ]; then
    strace -c -S calls -o results/A2_strace_wc.txt     wc -l "$LOG1" > /dev/null
    strace -c -S calls -o results/A2_strace_python.txt python3 count_one.py "$LOG1" > /dev/null
    { echo "wc -l — три самых частых вызова:";          top3 results/A2_strace_wc.txt
      echo "python3 count_one.py — три самых частых вызова:"; top3 results/A2_strace_python.txt
      echo; echo "Всего вызовов:"
      echo "  wc -l:    $(awk '$NF=="total"{print $4}' results/A2_strace_wc.txt)"
      echo "  python3:  $(awk '$NF=="total"{print $4}' results/A2_strace_python.txt)"; } | tee results/A2_top3.txt
else
    echo "strace не установлен — пропускаю. Установите: sudo apt install strace"
fi

echo
echo "=== B: parallel_logs.py (отчёт + проверка зомби) ==="
python3 parallel_logs.py -n 4 --check-zombies > results/B_report_and_zombies.txt 2>&1
sed -n '1p' results/B_report_and_zombies.txt
tail -4 results/B_report_and_zombies.txt

echo
echo "=== B: время при N = 1, 2, 4 (по 3 запуска) ==="
{ echo "Ядер процессора: $(nproc)"
  for n in 1 2 4; do
      for i in 1 2 3; do timeit "N=$n запуск $i" python3 parallel_logs.py -n "$n" --quiet; done
  done; } | tee results/B_timing.txt

echo
echo "=== C1: время трёх способов (N=4, по 3 запуска) ==="
{ echo "Ядер процессора: $(nproc)"
  for m in pipe shm tmp; do
      for i in 1 2 3; do timeit "$m запуск $i" python3 advanced.py --method "$m" -n 4 --quiet; done
  done; } | tee results/C1_timing.txt

echo
echo "=== C1: strace -f -c для каждого способа ==="
if [ "$have_strace" -eq 1 ]; then
    for m in pipe shm tmp; do
        strace -f -c -S calls -o "results/C1_strace_$m.txt" python3 advanced.py --method "$m" -n 4 --quiet 2>/dev/null
        echo "$m: всего вызовов $(awk '$NF=="total"{print $4}' "results/C1_strace_$m.txt"), топ-3:"
        top3 "results/C1_strace_$m.txt"
    done
else
    echo "strace не установлен — пропускаю."
fi

echo
echo "=== C2: проверка Ctrl+C ==="
bash test_ctrl_c.sh > results/C2_ctrl_c_test.txt 2>&1
grep -E "метод:|код выхода|ПОСЛЕ" -A1 results/C2_ctrl_c_test.txt | grep -v '^--$' | head -40

echo
echo "=== C3: начало и конец сбоя ==="
python3 incident.py | tee results/C3_incident.txt

echo
echo "=== Зомби после всех запусков ==="
ps -eo pid,ppid,stat,comm | awk 'NR==1 || $3 ~ /^Z/' | tee results/zombies_after.txt
if [ "$(wc -l < results/zombies_after.txt)" -le 1 ]; then echo "Зомби нет."; fi

echo
echo "Готово. Все результаты лежат в папке results/"
