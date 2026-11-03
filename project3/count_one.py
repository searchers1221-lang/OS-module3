#!/usr/bin/env python3
"""Задача A2: свой подсчёт строк на одном файле (для сравнения с wc -l под strace)."""
import sys

n = 0
with open(sys.argv[1], encoding="utf-8") as f:
    for _ in f:
        n += 1
print(n)
