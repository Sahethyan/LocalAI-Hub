# LocalAI Hub

Lightweight local AI web interface: **FastAPI + vanilla frontend** on Raspberry Pi, with **Ollama on a separate laptop** over LAN.

## Phase 1 — Quick start

```bash
cd "LocalAI Hub"
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Edit .env — set OLLAMA_BASE_URL to your laptop IP

python scripts/init_db.py
uvicorn app.main:app --host 0.0.0.0 --port 8080
```

Verify:

```bash
curl http://localhost:8080/api/v1/health
# {"status":"ok"}
```

Logs are written to `logs/app.log`. OpenAPI docs: `http://<pi-ip>:8080/docs`.

## Project layout

See [IMPLEMENTATION_PLAN.md](IMPLEMENTATION_PLAN.md) for the full phase-by-phase build guide.

## Configuration

All settings are loaded from `.env` via `app/config/settings.py`. Copy `.env.example` and adjust `OLLAMA_BASE_URL`, `LAN_ONLY`, and `ALLOWED_SUBNETS` for your network.

Phase 0 (Pi OS + Ollama on laptop) can be done later; Phase 1 runs without a live Ollama connection.
