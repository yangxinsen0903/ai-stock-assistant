#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "$0")"

if ! command -v python3 >/dev/null 2>&1; then
  echo "❌ python3 not found. Please install Python 3.11+ first."
  exit 1
fi

if [ -d .venv ] && [ ! -f .venv/bin/activate ]; then
  echo "⚠️ Found broken .venv (missing bin/activate), recreating..."
  rm -rf .venv
fi

if [ ! -f .venv/bin/activate ]; then
  echo "📦 Creating virtualenv (.venv)..."
  if ! python3 -m venv .venv; then
    echo "❌ Failed to create venv. On Debian/Ubuntu run: sudo apt install python3-venv"
    exit 1
  fi
fi

# shellcheck disable=SC1091
source .venv/bin/activate

echo "📦 Installing dependencies..."
python -m pip install --upgrade pip
if [ -f requirements.local.txt ]; then
  python -m pip install -r requirements.local.txt
else
  python -m pip install -r requirements.txt
fi

if [ ! -f .env ]; then
  echo "🧩 Creating .env from .env.sqlite.example"
  cp .env.sqlite.example .env
fi

# Auto-fix common local mismatch: postgres DSN without psycopg2 installed.
if grep -q '^DATABASE_URL=postgresql+psycopg2://' .env; then
  echo "⚠️ Detected postgres+psycopg2 DATABASE_URL in .env; switching to SQLite for local run."
  sed -i 's#^DATABASE_URL=.*#DATABASE_URL=sqlite:///./aistock.db#' .env
fi

export PYTHONPATH=.

if command -v ss >/dev/null 2>&1 && ss -ltn '( sport = :8000 )' | grep -q ':8000'; then
  echo "ℹ️ Backend already running on 127.0.0.1:8000 (port in use)."
  echo "   You can verify with: ./verify_api.sh"
  exit 0
fi

echo "🚀 Starting backend at http://127.0.0.1:8000"
exec uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
