# LocalAI Hub — Implementation Plan

A phase-by-phase guide to building a lightweight local AI web interface: **FastAPI + vanilla frontend on Raspberry Pi Zero W**, with **LLM inference on a separate laptop via Ollama** over the local WiFi network.

### Phase progress

- [ ] **Phase 0** — Prerequisites & Environment
- [x] **Phase 1** — Project Scaffold & Configuration
- [x] **Phase 2** — Database Layer
- [x] **Phase 3** — Ollama Integration Service
- [x] **Phase 4** — Streaming Chat API
- [x] **Phase 5** — Frontend: Core UI
- [x] **Phase 6** — Sidebar, History & UX Polish
- [ ] **Phase 7** — System Monitor & Health Pages
- [ ] **Phase 8** — Security, Rate Limiting & REST API
- [ ] **Phase 9** — Deployment & Operations
- [ ] **Phase 10** — Extra Features & Optimization
- [ ] **Phase 11** — Testing & Documentation

---

## Architecture Overview

```
┌─────────────┐     HTTP/WS      ┌──────────────────────┐     HTTP (LAN)     ┌─────────────────┐
│   Browser   │ ───────────────► │  Raspberry Pi Zero W │ ────────────────► │  Laptop (Ollama) │
│ (phone/PC)  │ ◄─────────────── │  FastAPI + UI + DB   │ ◄──────────────── │  :11434/api/*    │
└─────────────┘                  └──────────────────────┘                    └─────────────────┘
```

| Component | Runs on | Responsibility |
|-----------|---------|----------------|
| HTML/CSS/JS UI | Pi | Chat UI, settings, monitoring |
| FastAPI backend | Pi | Proxy, SQLite, auth, streaming |
| Ollama | Laptop | Model load, inference, GPU/CPU |

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
│   ├── models/
│   │   ├── __init__.py
│   │   └── database.py         # SQLAlchemy models (Chat, Message)
│   ├── schemas/
│   │   ├── __init__.py
│   │   ├── chat.py
│   │   ├── ollama.py
│   │   └── settings.py
│   ├── routers/
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── chat.py         # REST + streaming endpoints
│   │   │   ├── models.py       # Ollama model list proxy
│   │   │   ├── health.py
│   │   │   ├── system.py       # Pi CPU/RAM/network
│   │   │   ├── settings_api.py
│   │   │   └── export.py       # Import/export history
│   │   └── ws.py               # WebSocket streaming (optional path)
│   ├── services/
│   │   ├── __init__.py
│   │   ├── ollama_client.py    # httpx async client to laptop
│   │   ├── chat_service.py     # CRUD + streaming orchestration
│   │   ├── reconnect.py        # Auto-reconnect / health polling
│   │   └── system_monitor.py   # psutil for Pi stats
│   └── utils/
│       ├── __init__.py
│       ├── logging.py
│       ├── rate_limit.py
│       ├── auth.py             # Basic auth + API key
│       └── lan_check.py        # LAN-only middleware helper
├── templates/
│   ├── base.html
│   ├── chat.html
│   ├── settings.html
│   ├── monitor.html
│   └── partials/
│       ├── sidebar.html
│       └── message.html
├── static/
│   ├── css/
│   │   ├── main.css
│   │   └── themes.css          # light/dark variables
│   ├── js/
│   │   ├── app.js              # core init, theme, sidebar
│   │   ├── chat.js             # fetch/stream, history
│   │   ├── markdown.js         # marked.js or lightweight MD
│   │   └── highlight.js        # prism/highlight.js (minimal build)
│   └── img/
├── database/
│   └── .gitkeep                # SQLite file lives here at runtime
├── logs/
│   └── .gitkeep
├── deploy/
│   ├── localai-hub.service     # systemd unit
│   ├── setup.sh
│   └── docker/                 # optional
│       ├── Dockerfile
│       └── docker-compose.yml
├── scripts/
│   └── init_db.py              # SQLite schema bootstrap
├── .env.example
├── requirements.txt
├── README.md
└── IMPLEMENTATION_PLAN.md      # this file
```

---

## [ ] Phase 0 — Prerequisites & Environment (Day 0)

**Goal:** Both Pi and laptop are ready on the same LAN before any code is written.

### Raspberry Pi Zero W
- [ ] Flash **Raspberry Pi OS Lite** (64-bit if supported, else 32-bit)
- [ ] Enable SSH, set hostname (e.g. `localai-hub`)
- [ ] Connect to WiFi; assign **static DHCP lease** or reserved IP on router
- [ ] Update system: `sudo apt update && sudo apt full-upgrade -y`
- [ ] Install Python 3.11+ (or distro default), `python3-venv`, `git`
- [ ] Optional Pi tuning (document in README):
  - Disable unused services (Bluetooth if unused)
  - `gpu_mem=16` in `/boot/firmware/config.txt` if applicable
  - Swap size 512MB–1GB only if needed (Pi Zero W has 512MB RAM)

### Laptop (Ollama host)
- [ ] Install [Ollama](https://ollama.com)
- [ ] Pull at least one small model for testing (e.g. `llama3.2:1b`, `phi3:mini`)
- [ ] Bind Ollama to LAN (not only localhost):
  - Set `OLLAMA_HOST=0.0.0.0:11434` in environment or systemd
- [ ] Confirm firewall allows **TCP 11434** from Pi subnet
- [ ] Test from Pi: `curl http://<LAPTOP_IP>:11434/api/tags`

### Network
- [ ] Document Pi IP, laptop IP, and port plan (e.g. Pi `:8080`, Ollama `:11434`)
- [ ] Verify phone/laptop browser can reach `http://<PI_IP>:8080` after Phase 4

**Deliverable:** Network checklist in README; both machines can ping each other.

---

## [x] Phase 1 — Project Scaffold & Configuration (Days 1–2) ✅

**Status:** Completed

**Goal:** Runnable empty FastAPI app with config, logging, and folder layout.

### Tasks
1. **Initialize repository**
   - Create folder structure above
   - `python3 -m venv venv` on Pi
   - `requirements.txt` with pinned minimal deps:

     | Package | Purpose |
     |---------|---------|
     | fastapi | API framework |
     | uvicorn[standard] | ASGI server |
     | sqlalchemy | ORM |
     | aiosqlite | async SQLite driver |
     | httpx | async Ollama HTTP |
     | pydantic-settings | `.env` loading |
     | python-multipart | forms if needed |
     | jinja2 | templates |
     | python-dotenv | env file |
     | psutil | Pi system stats |
     | slowapi or custom | rate limiting |

   - Avoid: heavy ML libs, Redis, Celery, React build chain

2. **`app/config/settings.py`**
   - `OLLAMA_BASE_URL` (default `http://192.168.1.100:11434`)
   - `HOST`, `PORT`, `BIND` (`0.0.0.0`)
   - `DATABASE_URL` (`sqlite+aiosqlite:///./database/localai.db`)
   - `LAN_ONLY`, `ALLOWED_SUBNETS` (optional CIDR list)
   - `BASIC_AUTH_USER`, `BASIC_AUTH_PASSWORD` (optional)
   - `API_KEY` (optional REST key)
   - `LOG_LEVEL`, `LOG_FILE`
   - `RATE_LIMIT_PER_MINUTE`

3. **`app/utils/logging.py`**
   - Rotating file handler → `logs/app.log`
   - Console handler for development

4. **`app/main.py`**
   - FastAPI app factory
   - Mount `StaticFiles`, `Jinja2Templates`
   - CORS (restrict origins in LAN-only mode)
   - Lifespan: DB init, httpx client pool
   - Include routers under `/api/v1`
   - OpenAPI at `/docs` and `/redoc`

5. **`.env.example`** — document every variable with comments

6. **`scripts/init_db.py`** — create tables: `chats`, `messages`

**Verification**
```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080
curl http://localhost:8080/api/v1/health
```

**Deliverable:** Health endpoint returns `{"status":"ok"}`; logs write to `logs/`.

---

## [x] Phase 2 — Database Layer (Day 2–3) ✅

**Status:** Completed

**Goal:** Persistent chat history on Pi only (no cloud).

### Schema (SQLAlchemy)

| Table | Fields |
|-------|--------|
| `chats` | `id`, `title`, `model`, `created_at`, `updated_at` |
| `messages` | `id`, `chat_id`, `role` (user/assistant/system), `content`, `created_at` |

### Tasks
1. Define models in `app/models/database.py`
2. Async session factory (`async_sessionmaker`)
3. `app/services/chat_service.py`:
   - Create chat, list chats, get messages
   - Append user/assistant messages after stream completes
   - Auto-title from first user message (truncate 50 chars)
4. Pydantic schemas in `app/schemas/chat.py` for request/response

**Verification**
- Unit-style manual test: create chat via Python shell or temporary route
- Confirm SQLite file under `database/localai.db`

**Deliverable:** CRUD works; no UI yet.

---

## [x] Phase 3 — Ollama Integration Service (Days 3–4) ✅

**Status:** Completed

**Goal:** Pi proxies all inference to laptop; Pi never loads models.

### `app/services/ollama_client.py`

| Method | Ollama endpoint | Notes |
|--------|-----------------|-------|
| `list_models()` | `GET /api/tags` | Cache 30–60s on Pi to reduce LAN traffic |
| `generate_stream()` | `POST /api/chat` or `/api/generate` | Prefer `/api/chat` for message arrays |
| `health_check()` | `GET /api/tags` or HEAD | Short timeout (2–3s) |

### Implementation details
- Use **httpx.AsyncClient** with timeouts and connection limits (max 2–4 connections on Pi Zero W)
- Parse **NDJSON** stream from Ollama (`application/x-ndjson`)
- Yield tokens to FastAPI `StreamingResponse` or WebSocket sender
- Map errors: connection refused → `503` with clear message to UI

### `app/services/reconnect.py`
- Background task (asyncio): poll Ollama every N seconds (configurable, default 10s)
- Expose status: `online` | `offline` | `degraded`
- Store last successful ping timestamp

### Routers
- `GET /api/v1/models` — proxy model list
- `GET /api/v1/ollama/status` — connection indicator data

**Verification**
```bash
curl http://<PI>:8080/api/v1/models
# Stream test via /api/v1/chat/completions or dedicated stream route
```

**Deliverable:** Model list and one-shot generate work from Pi to laptop.

---

## [x] Phase 4 — Streaming Chat API (Days 4–6) ✅

**Status:** Completed

**Goal:** Real-time token streaming to browser with history persistence.

### API design (versioned `/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/chat` | Create new chat |
| GET | `/chats` | List sidebar chats |
| GET | `/chats/{id}` | Messages for chat |
| DELETE | `/chats/{id}` | Delete chat |
| POST | `/chats/{id}/messages` | Send message + stream reply |

### Streaming options (implement both for flexibility)

1. **SSE (Server-Sent Events)** — recommended for Pi Zero W simplicity  
   - `Content-Type: text/event-stream`  
   - Events: `token`, `done`, `error`  
   - Frontend: `fetch` + `ReadableStream` reader

2. **WebSocket** — `app/routers/ws.py`  
   - Bidirectional; good for typing indicators and reconnect  
   - Same token protocol as SSE

### Flow
1. Client sends message + `model` + optional `chat_id`
2. Save user message to SQLite
3. Build Ollama payload from last N messages (context window limit in settings)
4. Stream from Ollama → forward each chunk → client
5. On `done`, save full assistant message to SQLite

### Pydantic validation
- Max message length (e.g. 32k chars)
- Model name whitelist from last `/models` fetch (soft validation)

**Deliverable:** `curl` or minimal HTML page can stream a reply end-to-end.

---

## [x] Phase 5 — Frontend: Core UI (Days 6–9) ✅

**Status:** Completed

**Goal:** ChatGPT-like dark UI; no React/Vue; minimal JS footprint.

### Templates (Jinja2)
- `base.html` — meta viewport, CSS links, `theme` class on `<html>`
- `chat.html` — main layout: sidebar + message area + input
- `partials/sidebar.html` — chat list, new chat, links to settings/monitor

### CSS (`static/css/main.css`)
- CSS variables for dark/light themes
- Flex/grid layout: collapsible sidebar on mobile (hamburger)
- Chat bubbles: user right, assistant left
- Sticky input bar, auto-resize textarea
- Connection badge (green/red) in header

### JavaScript (`static/js/chat.js`)
- `fetch` POST to stream endpoint; parse SSE/NDJSON
- Append tokens to current assistant bubble (typing effect)
- Auto-scroll to bottom on new content
- Model dropdown populated from `/api/v1/models`
- Loading spinner while waiting for first token
- Debounce rapid sends

### Libraries (CDN or vendored minimal builds)
- **marked** (~small) for Markdown
- **highlight.js** — load only common languages (python, js, bash, json) to save RAM

**Deliverable:** Full chat loop in browser on phone and desktop.

---

## [x] Phase 6 — Sidebar, History & UX Polish (Days 9–11) ✅

**Status:** Completed

**Goal:** Complete main features 1–11 from requirements.

### Tasks
| Feature | Implementation |
|---------|----------------|
| Chat history | Load `/api/v1/chats` on init; click loads messages |
| New chat | POST `/chat`; clear UI state |
| Delete chat | DELETE + remove from sidebar |
| Typing animation | CSS blink cursor on streaming bubble |
| Markdown | Run `marked.parse` on complete message; stream plain text then MD on done |
| Code highlight | `hljs.highlightElement` after MD render |
| Settings page | Form: Ollama URL, port, context length; POST to `/api/v1/settings` |
| Persist settings | SQLite `settings` table or JSON file in `database/` |
| Theme toggle | `localStorage` + CSS class; no server round-trip |
| Export/import | Phase 8 |

**Deliverable:** Sidebar navigation works; settings change Ollama IP without restart if hot-reload supported.

---

## [ ] Phase 7 — System Monitor & Health Pages (Days 11–12)

**Goal:** Requirements 13 + connection status (5, 12).

### `app/services/system_monitor.py` (psutil)
- CPU % (1s interval sample)
- RAM used/total MB
- Disk optional (light)
- Network: default gateway reachable, WiFi SSID if available (`iwgetid` subprocess optional)

### Routes & page
- `GET /api/v1/system/stats` — JSON for AJAX refresh every 5s
- `GET /monitor` — Jinja template with simple gauges (CSS bars, no Chart.js if avoidable)

### Ollama status on monitor page
- Reuse reconnect service state + latency ms

**Deliverable:** Monitor page updates without full page reload.

---

## [ ] Phase 8 — Security, Rate Limiting & REST API (Days 12–14)

**Goal:** Requirements 14–15, security section, API keys.

### Security
| Control | Implementation |
|---------|----------------|
| Input validation | Pydantic max lengths, strip null bytes |
| Rate limiting | slowapi or middleware: per-IP requests/min |
| LAN-only | Middleware: reject if client IP not in `ALLOWED_SUBNETS` |
| Basic auth | `HTTPBasic` dependency on all HTML routes if enabled |
| API key | Header `X-API-Key` on `/api/v1/*` when `API_KEY` set |

### External REST API
- Document in OpenAPI (`/docs`)
- Endpoints mirror UI: chats, messages, stream, models, health
- Version prefix: `/api/v1` — future `/api/v2` without breaking v1

### Export / import
- `GET /api/v1/export` — JSON dump all chats
- `POST /api/v1/import` — merge or replace with validation

**Deliverable:** Postman collection or README examples for external apps.

---

## [ ] Phase 9 — Deployment & Operations (Days 14–16)

**Goal:** Production run on Pi OS Lite with auto-start.

### `deploy/setup.sh`
- Create venv, `pip install -r requirements.txt`
- Run `scripts/init_db.py`
- Copy `.env.example` → `.env` if missing
- Set permissions on `database/`, `logs/`

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

**Note:** Use `--workers 1` on Pi Zero W (single core).

### README sections
- Installation (step-by-step for beginners)
- Finding laptop IP (`ip a` on Linux)
- Ollama `OLLAMA_HOST` setup
- systemd enable/start
- **Troubleshooting:** cannot connect to Ollama, port in use, SQLite locked, out of memory

### Optional Docker
- Multi-stage not needed; slim Python image
- Volume mounts for `database/`, `logs/`, `.env`
- Document as optional — native venv preferred on Pi Zero W

**Deliverable:** Reboot Pi → service starts → UI accessible on LAN.

---

## [ ] Phase 10 — Extra Features & Optimization (Days 16–18)

**Goal:** Polish, Pi-specific tuning, optional extras.

### QR code access
- `GET /api/v1/qr` or settings page embed
- Generate PNG/SVG for `http://<pi-ip>:8080` using `qrcode` lib (lightweight) or external API off by default

### Performance (Pi Zero W)
| Area | Tactic |
|------|--------|
| RAM | Single uvicorn worker; limit concurrent streams to 1–2 |
| CPU | Gzip only for static assets; minify CSS/JS once at build |
| Network | Cache model list; compress JSON responses |
| SQLite | WAL mode; indexes on `chat_id`, `created_at` |
| Frontend | No framework; defer highlight.js until message complete |
| Streaming | Small chunk buffer; avoid accumulating full response in RAM twice |

### Auto-reconnect UX
- Frontend polls `/api/v1/ollama/status` every 5s
- Disable send button when offline; show banner "Reconnecting to Ollama…"

### WebSocket parity
- Ensure WS path matches SSE feature set for external apps

**Deliverable:** Stable 24h run without OOM; README "Optimization" section.

---

## [ ] Phase 11 — Testing & Documentation (Days 18–20)

**Goal:** Confidence for real-world use.

### Manual test matrix
| Test | Device |
|------|--------|
| New chat + stream | Phone Safari/Chrome |
| Switch model mid-session | Laptop browser |
| Change Ollama IP in settings | Pi |
| Kill Ollama on laptop → UI shows offline | Any |
| Restart Ollama → auto reconnect | Any |
| Basic auth enabled | Phone |
| API key REST call | curl / Postman |
| Export then import history | Desktop |
| systemd restart | Pi headless |

### Documentation
- README: architecture diagram (ASCII or mermaid)
- API examples for streaming (curl + JavaScript snippet)
- `.env.example` fully commented
- Security warnings: do not expose Pi to public internet without hardening

**Deliverable:** v1.0 tag; known limitations listed.

---

## Implementation Order Summary

| Phase | Focus | Depends on | Status |
|-------|--------|------------|--------|
| 0 | Network & Ollama on laptop | — | [ ] |
| 1 | Scaffold, config, health | 0 | [x] ✅ |
| 2 | SQLite + ORM | 1 | [x] ✅ |
| 3 | Ollama client + status | 0, 1 | [x] ✅ |
| 4 | Streaming API | 2, 3 | [x] ✅ |
| 5 | Frontend core chat | 4 | [x] ✅ |
| 6 | Sidebar, MD, settings UI | 5 | [x] |
| 7 | System monitor page | 1, 3 | [ ] |
| 8 | Auth, rate limit, REST export | 4 | [ ] |
| 9 | systemd, setup.sh, README deploy | 1–8 | [ ] |
| 10 | QR, optimizations, reconnect UX | 5–9 | [ ] |
| 11 | Testing & docs | All | [ ] |

---

## Key Technical Decisions

1. **SSE over WebSocket as default** — simpler `fetch` client; less memory than full WS stack on Pi; add WS for power users.
2. **Ollama `/api/chat`** — aligns with message history format; easier than raw `/api/generate`.
3. **Single worker uvicorn** — Pi Zero W cannot benefit from multiple workers.
4. **No inference on Pi** — hard rule: all `POST` generate paths call `ollama_client` only.
5. **Vanilla JS** — optional Alpine.js for settings toggles only if it stays under ~15KB gzipped.

---

## Risk Register

| Risk | Mitigation |
|------|------------|
| Pi OOM during stream | Cap concurrent requests; stream-through without buffering full body |
| Ollama bound to localhost on laptop | Document `OLLAMA_HOST=0.0.0.0` prominently |
| Slow WiFi on Pi Zero W | Keep payloads small; limit context messages sent to Ollama |
| SQLite write contention | WAL mode; single write per completed message |
| Large highlight.js | Load minimal language pack; highlight on idle/`requestIdleCallback` |

---

## Success Criteria (Definition of Done)

- [ ] Browser on LAN talks only to Pi; Pi talks to laptop Ollama
- [ ] Streaming chat works on mobile and desktop
- [ ] Chat history persists across Pi restarts
- [ ] Model dropdown reflects laptop's Ollama models
- [ ] Connection indicator reflects real Ollama reachability
- [ ] Settings page updates Ollama base URL
- [ ] Monitor page shows Pi CPU/RAM and Ollama status
- [ ] `/docs` documents versioned REST API
- [ ] systemd starts app on boot
- [ ] README enables a beginner to deploy end-to-end

---

## Next Step After This Plan

Phases **1–5** are complete. Continue with **Phase 6** (sidebar, history, and UX polish), then proceed sequentially through phases 7–11. Complete **Phase 0** prerequisites in parallel if not already done on your Pi and laptop.
