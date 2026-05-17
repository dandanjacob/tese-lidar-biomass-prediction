#!/bin/bash
# Inicia o dashboard usando o ambiente virtual do projeto.
# Use: bash app/run.sh  (a partir da raiz do projeto)
# Ou:  make app
set -e
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
exec "$ROOT/.venv/bin/streamlit" run "$ROOT/app/main.py" "$@"
