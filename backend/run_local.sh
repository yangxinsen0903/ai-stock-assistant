#!/usr/bin/env bash
set -euo pipefail

if [ ! -f .env ]; then
  cp .env.example .env
fi

export PYTHONPATH=.
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
