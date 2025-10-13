# ThreadSense

Context-aware Reddit thread summarization: KeyBERT keywords → LLM summarize → eval/metrics.

## Repo layout
- `src/` — original research pipeline (scripts, no packaging). See `AGENTS.md`.
- `backend/` — FastAPI + Celery + Postgres service (phases 1–4: ingestion, local NLP, LLM summaries/key-points/insights, search).
- `deploy/` — Docker Compose for Postgres 16 + pgvector and Redis.
- `docs/architecture.md` — system design.

## Running the backend
From `backend/` (venv at `backend/.venv`):

```
docker compose -f deploy/docker-compose.yml up -d   # postgres + redis
.venv/bin/alembic upgrade head                      # apply migrations
.venv/bin/uvicorn app.main:app --port 8000          # API
.venv/bin/celery -A celery_app worker               # background worker
```

Config is env-driven (`backend/app/config.py`), read from `.env` in the process CWD. Copy `deploy/.env.example` to `backend/.env` and set `LLM_API_KEY` (OpenAI-compatible) plus Reddit creds. Without `LLM_API_KEY` the summarize chain fails.

## API (all under `/api`)
`POST /threads/ingest` · `GET /threads` · `GET /threads/{id}` · `GET /threads/{id}/comments` · `GET /threads/{id}/summaries` · `GET /threads/{id}/participants` · `GET /search?q=` · `GET /health` · `GET /health/ready`
