#!/usr/bin/env bash
# Автоматическая проверка задания C2: запускаем медленно, «нажимаем Ctrl+C»
# (посылаем SIGINT всей группе процессов, как это делает терминал),
# затем проверяем: нет зомби, нет процессов, нет сегментов в /dev/shm и временных файлов.

set -m   # у каждого фонового задания своя группа процессов — как у программы в терминале

leftovers() {
    ls /dev/shm /tmp 2>/dev/null | grep -E '^(psm_|logs_)' || echo "(пусто)"
}
procs() {
    # python3 — наши процессы; STAT, начинающийся с Z, — зомби
    ps -eo pid,ppid,stat,comm | awk '$4 == "python3" || $3 ~ /^Z/' | grep . || echo "(пусто)"
}

for method in pipe shm tmp; do
    echo "################ метод: $method ################"
    python3 advanced.py --method "$method" -n 4 --delay 0.5 > /dev/null 2> "/tmp/ctrlc_$method.txt" &
    pid=$!
    sleep 1.5
    echo "--- ДО Ctrl+C: процессы (родитель + 4 ребёнка)"
    procs
    echo "--- ДО Ctrl+C: /dev/shm и /tmp"
    leftovers
    echo ">>> Ctrl+C"
    kill -INT -- "-$pid"
    wait "$pid" 2>/dev/null
    echo "код выхода программы: $?"
    sleep 0.5
    echo "--- ПОСЛЕ: процессы и зомби"
    procs
    echo "--- ПОСЛЕ: /dev/shm и /tmp"
    leftovers
    echo "--- сообщение программы:"
    cat "/tmp/ctrlc_$method.txt"
    echo
done

echo "################ сигнал только родителю (kill <pid>, дети не получают его сами) ################"
python3 advanced.py --method shm -n 4 --delay 0.5 > /dev/null 2> /tmp/ctrlc_x.txt &
pid=$!
sleep 1.5
kill -TERM "$pid"
wait "$pid" 2>/dev/null
sleep 0.5
echo "--- процессы и зомби"; procs
echo "--- /dev/shm и /tmp"; leftovers
cat /tmp/ctrlc_x.txt
rm -f /tmp/ctrlc_*.txt
