#!/bin/bash
# Скрипт для запуска бота без ручной активации venv
cd "$(dirname "$0")"
source test-env/bin/activate
python3 main.py

