# AI Stock Assistant v2

This package includes:
- `backend/`: runnable FastAPI backend
- `ios/AIStockAssistant/`: Xcode project for a SwiftUI iOS app

## What this is
A runnable MVP starter with:
- email/password auth
- holdings CRUD
- watchlist CRUD
- alerts CRUD
- AI assistant chat endpoint
- SwiftUI iOS client connected to backend

---

## 1) Fastest local start (recommended for testing)

### Backend with SQLite (no Docker, no Postgres)

```bash
cd backend
./run_dev.sh
```

Backend URLs:
- API: `http://127.0.0.1:8000`
- Swagger: `http://127.0.0.1:8000/docs`

If this is the first run, `run_dev.sh` will:
- create `.venv`
- install local dependencies (`requirements.local.txt`, SQLite path)
- create `.env` from `.env.sqlite.example`
- start uvicorn with reload

### One-command API verification
Open a second terminal:
```bash
cd backend
./verify_api.sh
```

It will verify:
1. `/healthz`
2. register/login
3. authenticated `/assistant/chat`

---

## 2) Docker mode (optional)

### Prerequisites
- Docker Desktop

### Commands
```bash
cd backend
cp .env.example .env
docker compose up --build
```

Health check:
```bash
curl http://localhost:8000/healthz
```

---

## 3) iOS app: run in Xcode

### Prerequisites
- Xcode 15+
- iOS Simulator

### Open project
```text
ios/AIStockAssistant/AIStockAssistant.xcodeproj
```

### First-time setup
Inside Xcode:
1. Select `AIStockAssistant` project
2. Signing & Capabilities → choose your Team
3. Adjust Bundle Identifier if needed
4. Pick an iPhone simulator
5. Run

### Backend URL config
Current config points to simulator localhost:
```swift
http://127.0.0.1:8000/api/v1
```
File:
```text
ios/AIStockAssistant/AIStockAssistant/Core/Config/AppConfig.swift
```

If testing on a real iPhone, replace with your Mac LAN IP:
```swift
static let apiBaseURL = "http://192.168.1.25:8000/api/v1"
```

---

## 4) Quick manual API test (optional)

Register:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/register \
  -H 'Content-Type: application/json' \
  -d '{"email":"alex@example.com","password":"Password123!"}'
```

Login:
```bash
curl -X POST http://127.0.0.1:8000/api/v1/auth/login \
  -H 'Content-Type: application/json' \
  -d '{"email":"alex@example.com","password":"Password123!"}'
```

---

## 5) Broker connect flow (Robinhood-style OAuth jump)

This MVP includes a broker-connection flow in **Settings**:
1. Tap **Connect Robinhood** (opens browser)
2. Complete auth callback
3. Return to app and tap **Sync Portfolio**
4. Portfolio tab refreshes with synced holdings

### Important
Current backend runs in **read-only portfolio mode** by default.
- No buy/sell/trading actions are implemented.
- Manual add/delete holdings APIs are blocked when read-only mode is enabled.
- Broker sync currently updates connection status only; real Robinhood position ingestion is still to be integrated.

## Notes
- Backend auto-creates tables on startup for quick local testing.
- AI endpoint uses OpenAI when `OPENAI_API_KEY` is set.
- Without key, assistant returns deterministic fallback text for end-to-end testing.
- `SessionStore` currently uses `UserDefaults`; production should move token storage to Keychain.
