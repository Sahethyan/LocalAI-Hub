# LocalAI Hub

Minimal LAN AI chat gateway for **Raspberry Pi Zero W**: FastAPI + vanilla JS on the Pi, **Ollama on a remote laptop**.

```
Browser → Pi (FastAPI + UI) → Laptop (Ollama API)
```

No database, no chat history, no settings UI — single-session streaming chat only.

## Quick start

```bash
cd "LocalAI Hub"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set OLLAMA_BASE_URL to your laptop IP

uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Open `http://<pi-ip>:8080` from a device on your LAN.

## API (`/api/v1`)

| Method | Path | Description |
|--------|------|-------------|
| POST | `/generate` | Stream chat via Ollama (NDJSON) |
| GET | `/models` | List models from Ollama |
| GET | `/health` | Pi liveness (+ CPU/RAM) |
| GET | `/status` | Ollama online/offline + latency |

## Configuration

All settings come from `.env` via `app/config/settings.py`. The only required change is `OLLAMA_BASE_URL`.

Run with a single worker on the Pi:

```bash
uvicorn app.main:app --host 0.0.0.0 --port 8080 --workers 1
```
