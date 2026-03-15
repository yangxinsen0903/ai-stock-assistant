#!/usr/bin/env bash
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:8000}"
EMAIL="${2:-tester@example.com}"
PASSWORD="${3:-Password123!}"

echo "== health =="
curl -s "$BASE_URL/healthz"
echo -e "\n"

echo "== register =="
REGISTER_JSON=$(curl -s -X POST "$BASE_URL/api/v1/auth/register" \
  -H 'Content-Type: application/json' \
  -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
echo "$REGISTER_JSON"
echo -e "\n"

TOKEN=$(printf '%s' "$REGISTER_JSON" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')

if [ -z "$TOKEN" ]; then
  echo "ℹ️ register may already exist, trying login..."
  LOGIN_JSON=$(curl -s -X POST "$BASE_URL/api/v1/auth/login" \
    -H 'Content-Type: application/json' \
    -d "{\"email\":\"$EMAIL\",\"password\":\"$PASSWORD\"}")
  echo "$LOGIN_JSON"
  TOKEN=$(printf '%s' "$LOGIN_JSON" | sed -n 's/.*"access_token"[[:space:]]*:[[:space:]]*"\([^"]*\)".*/\1/p')
fi

if [ -z "$TOKEN" ]; then
  echo "❌ Could not obtain token from register/login"
  exit 1
fi

echo "== assistant/chat =="
curl -s -X POST "$BASE_URL/api/v1/assistant/chat" \
  -H 'Content-Type: application/json' \
  -H "Authorization: Bearer $TOKEN" \
  -d '{"message":"我有5万元，偏稳健，怎么分批建仓？"}'
echo -e "\n✅ API verification finished"
