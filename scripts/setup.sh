#!/usr/bin/env bash
# Instalação do tiktok-ops no macOS/Linux.  Rode: bash scripts/setup.sh
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> Verificando Python"
PY=""
for cmd in python3.12 python3.11 python3 python; do
  if command -v "$cmd" >/dev/null 2>&1; then
    if "$cmd" -c 'import sys; raise SystemExit(0 if sys.version_info >= (3,11) else 1)'; then
      PY="$cmd"; break
    fi
  fi
done
[ -n "$PY" ] || { echo "Python 3.11 ou superior não encontrado."; exit 1; }
echo "    usando: $PY"

echo "==> Criando o ambiente virtual"
[ -d .venv ] || "$PY" -m venv .venv

echo "==> Instalando as dependências"
./.venv/bin/python -m pip install --upgrade pip --quiet
./.venv/bin/python -m pip install -e ".[dev]" --quiet

echo "==> Rodando os testes"
./.venv/bin/python -m pytest -q

[ -f .env ] || cp .env.example .env

echo
echo "Pronto. Ative com: source .venv/bin/activate"
echo "Depois experimente: tiktok-ops --help"
