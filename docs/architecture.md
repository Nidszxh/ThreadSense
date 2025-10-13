# ThreadSense Architecture

End-to-end system: ingest discussion threads, process them with local NLP,
summarize with an LLM, and surface everything through a web UI — with search,
background jobs, and observability.

**Status:** backend (phases 1–4) is built and verified; frontend (5) and
observability/deployment hardening (6) are planned.

```
Reddit / Forum / GitHub Discussion
             ↓
       Thread Ingestion          PRAW scraper + plugin interface, normalized Thread/Comment models
             ↓
      Context Processing         KeyBERT keywords + all-MiniLM-L6-v2 embeddings + participant stats (local)
             ↓
     NLP / LLM Pipeline          OpenAI-compatible LLM API: summary, key points, insights (Celery worker)
             ↓
     Summary + Insights          persisted models; pgvector + Postgres FTS search
             ↓
          Web UI                 React + Vite SPA → FastAPI REST API
```

## Principles

- **Hybrid compute.** Cheap/fast work runs locally with zero API cost:
  embeddings (`all-MiniLM-L6-v2`), KeyBERT keywords, participant/engagement
  stats, vector search. Only LLM *generation* goes to an API. This keeps the
  8GB laptop GPU out of the critical path (Falcon-7B already OOMs here).
- **Provider-agnostic LLM.** The generation service talks to an
  OpenAI-compatible `chat/completions` endpoint configured by env vars
  (`LLM_API_KEY`, `LLM_BASE_URL`, `LLM_MODEL`). Works with OpenAI, Groq, a
  local Ollama instance, etc. No vendor lock-in.
- **Async jobs, not request-time work.** Ingestion and analysis run as Celery
  tasks. API endpoints only read/write state; long work is enqueued and polled.
- **Research code stays.** `src/` remains the original script pipeline +
  evaluation harness. The service ports its algorithms (flattener,
  KeyBERT usage) rather than editing them in place.

## Stack

| Layer | Choice |
|---|---|
| API | FastAPI (Uvicorn), pydantic-settings, SQLAlchemy 2 + Alembic |
| DB | PostgreSQL 16 + `pgvector` (embeddings) + FTS (`tsvector`) |
| Jobs | Celery + Redis (broker & result backend, also cache) |
| Local NLP | sentence-transformers `all-MiniLM-L6-v2`, KeyBERT |
| LLM | OpenAI-compatible chat API (env-configured) |
| Frontend | React + Vite + TypeScript (planned, phase 5) |
| Obs | structured JSON logging, Prometheus metrics (planned, phase 6) |
| Deploy | Docker Compose: postgres + redis now; api/worker/frontend planned |

## Data model (Postgres)

- `threads` — `id`, `source` (reddit/github/forum), `source_id`, `title`, `url`,
  `author`, `created_at`, `status` (`pending|processing|completed|failed`),
  `error`, timestamps.
- `comments` — `id`, `thread_id`, `parent_id`, `author`, `body`, `depth`,
  `score`, `created_at`. Grows one row per comment.
- `comment_features` — one-to-one with `comments`: `keywords` (JSONB),
  `embedding` (`vector(384)`), `sentiment` (nullable, local model or LLM).
- `summaries` — `id`, `thread_id`, `kind` (`summary|key_points|insights`),
  `content` (JSONB/text), `model`, `tokens_in/out`, timestamps. One per kind per
  thread; latest wins (upsert).
- `participant_stats` — `thread_id`, `author`, `comment_count`, `avg_score`,
  `max_depth`, `is_root_author`, computed locally.

Search: `comments` body + `summaries` content get FTS indexes; `comment_features.embedding`
enables `ORDER BY embedding <=> :q ORDER BY ... LIMIT k` semantic search.

## Ingestion

- `IngestSource` protocol (`backend/app/ingest/base.py`):
  `fetch(url) -> RawThread`, `RawThread -> normalized Comment dicts`.
- **Reddit** is the first implementation, ported from
  `src/thread_collections/reddit_scraper_all_threads.py`: PRAW, `replace_more`,
  recursive reply walk → normalized `{author, body, score, depth, parent_id}`.
  Uses env-provided Reddit credentials (never hardcoded).
- Forum/GitHub-discussion adapters are stubs to fill later.
- Normalization means a single flattener (port of
  `thread_keyword_extraction.py:flatten_json_thread`) handles old/new shapes.

## NLP / context processing (local, runs in worker)

1. Flatten thread → comments.
2. Per comment: embedding via SentenceTransformer, keywords via KeyBERT
   (`keyphrase_ngram_range=(1,2)`, `top_n=10`), same knobs as the research code.
3. Thread-level stats: root/reply split, top comments by score, max depth,
   participant counts — pure SQL/computation, no model.
4. Store `comment_features` + `participant_stats`.

## LLM pipeline (worker)

For each thread, three generation tasks (all through the LLM client):
- **summary** — hierarchical local+global like `src/experiments/prompt_experiments.py`:
  group replies under roots, summarize each branch, then merge.
- **key_points** — bullet extraction from the branch summaries.
- **insights** — engagement/context observations (consensus, controversy,
  recurring keywords) combining LLM output with local stats.

Prompt templates live in `backend/app/nlp/prompts.py` (single source of truth,
mirroring the 4 research variants so experiments stay reproducible).

## API (FastAPI)

- `POST /api/threads/ingest` `{url}` → enqueues `ingest_thread` → returns thread id.
- `GET /api/threads` — list w/ status filter + pagination.
- `GET /api/threads/{id}` — thread + status + participant stats.
- `GET /api/threads/{id}/comments` — paginated comments (with keywords).
- `GET /api/threads/{id}/summaries` — the three summary kinds.
- `GET /api/search?q=` — FTS + semantic results (vector + keyword), backed by
  the `0002` migration's GIN indexes (`comments.body`, `summaries.content`).
- `GET /api/health`, `GET /api/health/ready` — liveness/readiness.

Client flow: POST ingest → poll thread status → fetch summaries when
`completed`.

## Frontend (React + Vite + TS) — planned, phase 5

- **Thread list** — recent threads, status badges, ingest form.
- **Thread detail** — summary, key points, insights tabs; comment tree with
  keyword chips and participant sidebar.
- **Search** — query box returning FTS + semantic hits.
- Talks to FastAPI only; no build-time coupling to backend.

## Observability — planned, phase 6

- Structured JSON logs (request id, thread id, task id) via logging config.
- `prometheus-fastapi-instrumentator` on `/metrics`; Celery task counters
  (started/succeeded/failed, latency) exported by the worker.

## Deployment

Current `deploy/docker-compose.yml` runs only `postgres` (pgvector image) and
`redis`. The API and worker run on the host against them (see README). A later
phase will add compose services for `api`, `worker`, and `frontend` (nginx
serving the built SPA, proxying `/api`). `deploy/.env.example` documents all
secrets: Reddit creds, `LLM_API_KEY`/`BASE_URL`/`MODEL`, DB/Redis URLs.

## Directory layout

```
backend/
  app/
    main.py            # FastAPI app factory
    config.py          # pydantic-settings (env-driven)
    db.py              # engine/session
    models/            # SQLAlchemy ORM
    schemas/           # Pydantic DTOs
    api/               # routers (threads, summaries, search, health)
    ingest/            # base.py, reddit.py, (github.py, forum.py stubs)
    nlp/               # embeddings.py, keywords.py, participants.py, prompts.py, llm_client.py
    tasks/             # celery app + ingest/summarize tasks
  celery_app.py
  requirements.txt
  Dockerfile
frontend/               # planned (phase 5)
  src/ ...             # Vite React app
  Dockerfile
deploy/
  docker-compose.yml
  .env.example
docs/architecture.md   # this file
data/                  # existing research artifacts + model cache
src/                   # original research pipeline (unchanged reference)
```

## Build phases

- **Phase 1 — Backend skeleton** ✅: package, config, SQLAlchemy models, Alembic,
  FastAPI app with health routes, compose for postgres+redis.
- **Phase 2 — Ingestion + local NLP** ✅: Reddit plugin, flattener port, embedding
  + KeyBERT + participant services, Celery `ingest_thread`/`process_thread`.
- **Phase 3 — LLM pipeline** ✅: OpenAI-compatible client, prompt templates,
  summary/key-points/insight tasks, `summaries` + status wiring.
- **Phase 4 — Search** ✅: FTS + pgvector queries and `GET /api/search`.
- **Phase 5 — Frontend**: React app (list, detail, search, ingest).
- **Phase 6 — Hardening**: observability, cache headers, retries, Dockerfile
  polish, README/runbook.

Each phase ends with something runnable; phases 2–4 each add a working
end-to-end slice.
