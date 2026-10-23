#!/usr/bin/env bash
# Uruchomienie na Linuxie (Ubuntu Server) - odpowiednik run.bat.
# Tworzy .venv, gdy go brak, i instaluje zależności tylko po zmianie requirements.txt.
set -euo pipefail
cd "$(dirname "$(readlink -f "$0")")"

if [ ! -f .env ]; then
    echo "Brak pliku .env - skopiuj .env.example do .env i uzupełnij." >&2
    exit 1
fi

if [ ! -x .venv/bin/python ]; then
    if ! python3 -c 'import venv, ensurepip' >/dev/null 2>&1; then
        echo "Brak modułu venv. Zainstaluj: sudo apt install python3-venv" >&2
        exit 1
    fi
    echo "Tworzę .venv..."
    python3 -m venv .venv
fi
PYTHON=.venv/bin/python

hash_teraz="$(sha256sum requirements.txt | cut -d' ' -f1)"
hash_zapisany="$(cat .venv/.deps-hash 2>/dev/null || true)"
if [ "$hash_teraz" != "$hash_zapisany" ]; then
    echo "Instaluję zależności..."
    "$PYTHON" -m pip install --upgrade pip
    "$PYTHON" -m pip install -r requirements.txt
    echo "$hash_teraz" > .venv/.deps-hash
fi

PORT="$(grep -E '^EHF_PORT=' .env | tail -n1 | cut -d= -f2 | tr -d '\r[:space:]' || true)"
echo "EHF: http://$(hostname -I 2>/dev/null | awk '{print $1}'):${PORT:-5151}"
exec "$PYTHON" app.py
