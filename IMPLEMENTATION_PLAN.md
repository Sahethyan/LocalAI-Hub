# LocalAI Hub — Implementation Plan

A phase-by-phase guide to building a **lightweight, stateless AI terminal** on **Raspberry Pi Zero W**: FastAPI gateway + vanilla frontend on the Pi, with **LLM inference on a separate laptop via Ollama** over the local WiFi network.

**There is no database, no chat history, and no persistence.** Each request is independent; the Pi is only a streaming proxy and UI server.

### Phase progress

- [ ] **Phase 0** — Prerequisites
- [x] **Phase 1** — Project Scaffold *(existing scaffold may need cleanup: remove DB/SQLAlchemy)*
- [x] **Phase 2** — Ollama Integration *(simplify to proxy + status only)*
- [x] **Phase 3** — Streaming API *(refactor to stateless `POST /generate`)*
- [ ] **Phase 4** — Lightweight Frontend *(remove sidebar, history, settings)*
- [ ] **Phase 5** — System Monitor (basic)
- [ ] **Phase 6** — Security & Deployment (minimal)
- [ ] **Phase 7** — Testing & Documentation

---

## Architecture Overview

```
┌─────────────┐     HTTP (LAN)     ┌──────────────────────┐     HTTP (LAN)     ┌─────────────────┐
│   Browser   │ ────────────────► │  Raspberry Pi Zero W │ ────────────────► │  Laptop (Ollama) │
│ (phone/PC)  │ ◄──────────────── │  FastAPI + UI        │ ◄──────────────── │  :11434/api/*    │
└─────────────┘                   └──────────────────────┘                    └─────────────────┘
```

| Component | Runs on | Responsibility |
|-----------|---------|----------------|
| FastAPI backend | Pi | Streaming proxy + UI |
| HTML/CSS/JS | Pi | Single chat UI |
| Ollama | Laptop | Model inference |

**Data flow:** Browser sends a prompt to the Pi → Pi forwards to Ollama on the laptop → tokens stream back through the Pi to the browser. Nothing is stored on the Pi except logs (optional).

---

## Target Project Structure

```
LocalAI-Hub/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app entry, lifespan, middleware
│   ├── config/
│   │   ├── __init__.py
│   │   └── settings.py         # Pydantic Settings from .env
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── generate.py         # Request/response for /generate
│   │   └── ollama.py           # Ollama proxy types
│   ├── routers/
│   │   ├── __init__.py
│   │   └── v1/
│   │       ├── __init__.py
│   │       ├── generate.py     # POST /generate (SSE stream)
│   │       ├── models.py       # GET /models
│   │       ├── health.py       # GET /health
│   │       └── status.py       # GET /status (Ollama online/offline)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ollama_client.py    # httpx async client to laptop
│   │   └── system_monitor.py   # psutil for Pi stats (optional)
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       └── lan_check.py        # LAN-only middleware helper (optional)
├── templates/
│   ├── base.html
│   └── chat.html               # Single page only
├── static/
│   ├── css/
│   │   ├── main.css
│   │   └── themes.css          # light/dark variables
│   └── js/
│       ├── app.js              # theme toggle, status poll
│       └── chat.js             # fetch + SSE stream, model dropdown
├── logs/
│   └── .gitkeep
├── deploy/
│   ├── localai-hub.service     # systemd unit
│   └── setup.sh
├── .env.example
├── requirements.txt
├── README.md
└── IMPLEMENTATION_PLAN.md      # this file
```

**Removed from the old design:** `database/`, `models/database.py`, `chat_service.py`, `settings_api.py`, `export.py`, `ws.py`, sidebar/settings/monitor templates, `scripts/init_db.py`, SQLAlchemy/aiosqlite.

---

## API (`/api/v1/`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate` | Stream response from Ollama (SSE preferred) |
| GET | `/models` | List models from laptop (`GET /api/tags` proxy) |
| GET | `/health` | Pi process health (`{"status":"ok"}`) |
| GET | `/status` | Ollama reachability: online/offline + latency ms |

**No** chat, message, `chat_id`, CRUD, export/import, or settings endpoints.

### `POST /generate` (conceptual)

**Request body:**
```json
{
  "model": "llama3.2:1b",
  "prompt": "Hello",
  "messages": [{"role": "user", "content": "Hello"}]
}
```

Use `messages` when calling Ollama `/api/chat`; use `prompt` for `/api/generate` if you prefer that API. The Pi does not persist either form.

**Response:** `text/event-stream` (SSE) with events such as `token`, `done`, `error` — or raw NDJSON passthrough with `Content-Type` documented in README.

---

## [ ] Phase 0 — Prerequisites

**Goal:** Pi and laptop ready on the same LAN before writing code.

### Raspberry Pi Zero W
- [ ] Flash **Raspberry Pi OS Lite** (32-bit or 64-bit if supported)
- [ ] Enable SSH; set hostname (e.g. `localai-hub`)
- [ ] WiFi with **static DHCP lease** or reserved IP on the router
- [ ] Update: `sudo apt update && sudo apt full-upgrade -y`
- [ ] Install Python 3.11+ (or distro default), `python3-venv`, `git`
- [ ] Optional tuning (document in README):
  - Disable unused services (e.g. Bluetooth)
  - `gpu_mem=16` in `/boot/firmware/config.txt` if applicable
  - Swap 512MB–1GB only if needed (512MB RAM on Pi Zero W)

### Laptop (Ollama host)
- [ ] Install [Ollama](https://ollama.com)
- [ ] Pull a small test model (e.g. `llama3.2:1b`, `phi3:mini`)
- [ ] Bind to LAN: `OLLAMA_HOST=0.0.0.0:11434`
- [ ] Firewall allows **TCP 11434** from Pi subnet
- [ ] From Pi: `curl http://<LAPTOP_IP>:11434/api/tags`

### Network
- [ ] Document Pi IP, laptop IP, ports (Pi `:8080`, Ollama `:11434`)
- [ ] After Phase 4, verify browser reaches `http://<PI_IP>:8080`

**Deliverable:** Network checklist in README; Pi and laptop can reach each other.

---

## [x] Phase 1 — Project Scaffold

**Goal:** Runnable minimal FastAPI app with config and logging. **No database.**

### Tasks
1. **Repository layout** — folders per structure above (no `database/`).
2. **`requirements.txt`** — minimal pinned deps:

   | Package | Purpose |
   |---------|---------|
   | fastapi | API framework |
   | uvicorn[standard] | ASGI server |
   | httpx | async Ollama HTTP |
   | pydantic-settings | `.env` loading |
   | jinja2 | templates |
   | python-dotenv | env file |
   | psutil | Pi stats (Phase 5) |

   **Avoid:** SQLAlchemy, aiosqlite, Redis, Celery, React, heavy ML libs.

3. **`app/config/settings.py`**
   - `OLLAMA_BASE_URL` (e.g. `http://192.168.1.100:11434`)
   - `HOST`, `PORT`, `BIND` (`0.0.0.0`)
   - `LOG_LEVEL`, `LOG_FILE`
   - Optional: `LAN_ONLY`, `ALLOWED_SUBNETS`

4. **`app/utils/logging.py`** — rotating file + console handlers.

5. **`app/main.py`**
   - FastAPI factory
   - Mount `StaticFiles`, `Jinja2Templates`
   - Lifespan: single shared `httpx.AsyncClient` (no DB init)
   - Routers under `/api/v1`
   - Optional OpenAPI at `/docs`

6. **`.env.example`** — document all variables.

**Verification**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1
curl http://localhost:8080/api/v1/health
```

**Deliverable:** `GET /health` returns `{"status":"ok"}`.

**Refactor note:** If the repo still has SQLAlchemy, `init_db.py`, or chat routers, remove them in this phase.

---

## [x] Phase 2 — Ollama Integration

**Goal:** Pi proxies inference to the laptop only; Pi never loads models.

### `app/services/ollama_client.py`

| Method | Ollama endpoint | Notes |
|--------|-----------------|-------|
| `list_models()` | `GET /api/tags` | Cache 30–60s on Pi to reduce LAN traffic |
| `generate_stream()` | `POST /api/chat` or `/api/generate` | NDJSON stream |
| `health_check()` | `GET /api/tags` | Short timeout (2–3s); used for `/status` |

### Implementation
- **httpx.AsyncClient** — low connection limit (2–4) for Pi Zero W
- Parse Ollama **NDJSON** (`application/x-ndjson`)
- Connection errors → `503` with a clear message for the UI

### Routers
- `GET /api/v1/models` — proxy model list
- `GET /api/v1/status` — `{ "online": true|false, "latency_ms": number }`

**Verification**
```bash
curl http://<PI>:8080/api/v1/models
curl http://<PI>:8080/api/v1/status
```

**Deliverable:** Model list and Ollama status work from Pi to laptop.

---

## [x] Phase 3 — Streaming API (stateless)

**Goal:** One streaming endpoint; no persistence.

### Endpoint
- **`POST /api/v1/generate`** — accept model + prompt/messages; stream from Ollama to client.

### Streaming
- **SSE (preferred)** on Pi Zero W: `Content-Type: text/event-stream`, events `token`, `done`, `error`
- Frontend: `fetch` + `ReadableStream` reader (no WebSocket required)

### Flow
1. Client POSTs JSON to `/generate`
2. Pi forwards to Ollama immediately
3. Pi streams chunks to browser
4. On completion, connection closes — **nothing written to disk**

### Validation
- Max message/prompt length (e.g. 32k chars)
- Optional soft check: model name exists in last `/models` response

**Verification**
```bash
curl -N -X POST http://<PI>:8080/api/v1/generate \
  -H "Content-Type: application/json" \
  -d '{"model":"llama3.2:1b","prompt":"Say hi"}'
```

**Deliverable:** End-to-end stream without any DB or chat IDs.

**Refactor note:** Replace old `/chats/*` routes with this single endpoint.

---

## [ ] Phase 4 — Lightweight Frontend

**Goal:** Single chat page; minimal JS and RAM use.

### Page (`templates/chat.html`)
- One layout: header + message area + input
- **No** sidebar, history list, chat switching, or settings page

### UI elements (only)
- Model dropdown (from `GET /api/v1/models`)
- Online/offline indicator (from `GET /api/v1/status`, poll every 5–10s)
- Dark/light mode toggle (`localStorage` + CSS class on `<html>`)
- Streaming chat bubbles + sticky input (textarea)
- Disable send when Ollama offline

### CSS (`static/css/main.css`, `themes.css`)
- CSS variables for dark/light
- User bubbles right, assistant left
- Connection badge in header (green/red)
- Mobile-friendly; no heavy frameworks

### JavaScript (`static/js/chat.js`, `app.js`)
- POST to `/api/v1/generate`; parse SSE
- Append tokens to current assistant bubble
- Auto-scroll on new content
- Debounce rapid sends
- Optional: lightweight Markdown render **after** stream completes (keep bundle small)

**Avoid:** marked/highlight.js unless vendored minimal builds; defer heavy libs.

**Deliverable:** Full chat loop on phone and desktop with no persistence.

---

## [ ] Phase 5 — System Monitor (basic)

**Goal:** Simple visibility into Pi and Ollama — no extra product features.

### `app/services/system_monitor.py` (psutil)
- CPU % (sample over ~1s)
- RAM used/total MB
- Optional: disk usage (light)

### Optional minimal UI
- Small section on chat page or `GET /monitor` with CSS bar gauges (no Chart.js)
- AJAX poll `GET /api/v1/system/stats` every 5s if exposed
- Reuse `/api/v1/status` for Ollama line on the same view

**Deliverable:** Operator can see Pi load and Ollama status without SSH.

---

## [ ] Phase 6 — Security & Deployment (minimal)

**Goal:** Safe LAN deployment and boot-time start.

### Security (LAN-first)
| Control | Implementation |
|---------|----------------|
| Input validation | Pydantic max lengths on `/generate` |
| LAN-only (optional) | Middleware: client IP in `ALLOWED_SUBNETS` |
| Rate limit (optional) | Per-IP cap on `/generate` (simple middleware) |

**Out of scope for v1:** API keys, export/import, multi-user auth, public internet exposure.

### `deploy/setup.sh`
- Create venv; `pip install -r requirements.txt`
- Copy `.env.example` → `.env` if missing
- Ensure `logs/` writable

### `deploy/localai-hub.service`
```ini
[Unit]
Description=LocalAI Hub
After=network-online.target

[Service]
User=pi
WorkingDirectory=/home/pi/LocalAI-Hub
EnvironmentFile=/home/pi/LocalAI-Hub/.env
ExecStart=/home/pi/LocalAI-Hub/venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1
Restart=always

[Install]
WantedBy=multi-user.target
```

**Critical:** `--workers 1` on Pi Zero W (single core, 512MB RAM).

### README
- Install steps for beginners
- Laptop IP and `OLLAMA_HOST=0.0.0.0:11434`
- `systemctl enable --now localai-hub`
- Troubleshooting: Ollama unreachable, port in use, OOM

**Deliverable:** Reboot Pi → UI on LAN → stream works.

---

## [ ] Phase 7 — Testing & Documentation

**Goal:** Confidence for daily use on constrained hardware.

### Manual test matrix
| Test | Device |
|------|--------|
| Stream a prompt | Phone Safari/Chrome |
| Change model in dropdown | Desktop |
| Kill Ollama → offline indicator | Any |
| Restart Ollama → indicator green | Any |
| Toggle dark/light mode | Any |
| Refresh page → no old messages | Any |
| systemd restart | Pi headless |
| 1–2 hour run, no OOM | Pi |

### Documentation
- README architecture diagram (ASCII or mermaid)
- `curl` example for `/generate` SSE
- `.env.example` fully commented
- Warning: do not expose Pi to the public internet without hardening

**Deliverable:** v1.0 tag; known limitations (512MB RAM, single concurrent stream recommended).

---

## Implementation Order Summary

| Phase | Focus | Depends on |
|-------|--------|------------|
| 0 | Network & Ollama on laptop | — |
| 1 | Scaffold, config, health | 0 |
| 2 | Ollama client, models, status | 0, 1 |
| 3 | Stateless `POST /generate` | 2 |
| 4 | Single-page UI | 3 |
| 5 | Basic system monitor | 1, 2 |
| 6 | Deploy + minimal security | 1–4 |
| 7 | Tests & README | All |

---

## Key Design Decisions

1. **Stateless architecture** — no database anywhere; Pi is gateway + UI only.
2. **SSE streaming preferred** — simpler than WebSocket on Pi Zero W; standard `fetch` client.
3. **Single uvicorn worker** — Pi Zero W cannot usefully run multiple workers.
4. **Ollama only on laptop** — all inference via `ollama_client`; never load models on Pi.
5. **Minimal vanilla JS frontend** — no React/Vue; small static assets.
6. **No persistence layer** — refresh clears UI; optional `localStorage` for theme only.

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Pi OOM during stream | `--workers 1`; cap concurrent streams to 1–2; stream-through, do not buffer full body |
| Ollama on localhost only | Document `OLLAMA_HOST=0.0.0.0` |
| Slow Pi Zero W WiFi | Small payloads; short prompts for testing |
| Large frontend bundles | No frameworks; optional MD/highlight only after stream ends |

---

## Success Criteria (Definition of Done)

- [ ] Chat streaming works end-to-end (browser → Pi → Ollama → browser)
- [ ] Model selection from Ollama works (`GET /models`)
- [ ] Online/offline indicator works (`GET /status`)
- [ ] Dark/light mode works
- [ ] UI accessible over LAN on Pi `:8080`
- [ ] **No database exists anywhere** in the project
- [ ] Pi acts only as gateway UI server
- [ ] systemd starts app on boot
- [ ] README enables a beginner to deploy end-to-end

---

## Next Step

Align the codebase with this plan: **remove** SQLite, chat CRUD, sidebar, settings, and export paths; **keep and simplify** Ollama client and streaming toward `POST /api/v1/generate`. Then complete **Phase 4** (single-page UI), **Phase 5–7**, and **Phase 0** on real hardware if not done yet.
