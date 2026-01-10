#!/bin/bash
# Скрипт для запуска AgentOS без ручной активации venv
cd "$(dirname "$0")"
source test-env/bin/activate
python3 agentos_app.py
