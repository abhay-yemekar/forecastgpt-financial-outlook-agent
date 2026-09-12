# How to Run ForecastGPT

Step-by-step instructions from a fresh clone to a working product — locally
first, then options for going live.

---

## 0. Prerequisites

| Tool | Version | Why | Check |
|---|---|---|---|
| Python | 3.10–3.12 (3.14 is **not** supported — no `faiss-cpu` wheels) | Backend | `py -0` or `python --version` |
| Node.js + npm | 20+ (22 tested) | Frontend build | `node --version` |
| Docker Desktop | any recent | Redis (job queue); optional MySQL | `docker --version` |
| Ollama | 0.3+ | Local LLM (free) | `ollama --version` |

> **Windows note:** commands below are Git Bash syntax. In PowerShell, use
> `$env:REDIS_URL="..."` instead of `REDIS_URL=... cmd`.

---

## 1. Backend setup (one time)

```bash
cd forecastgpt-financial-outlook-agent

# Virtual environment with Python 3.10–3.12
py -3.10 -m venv .venv                 # or: python -m venv .venv
source .venv/Scripts/activate          # Windows Git Bash (.venv/bin/activate on Linux)

pip install -r requirements-dev.txt    # runtime + test deps (pytest, ruff)
```

Copy the env template and adjust if needed (defaults work out of the box):

```bash
cp .env.example .env
```

> **This project never assumes port 6379 is free.** Set `REDIS_PORT` in `.env`
> to any free port on your machine — the checked-in default is **6380**,
> chosen specifically because 6379 is commonly already in use by other local
> services. Keep `REDIS_URL` in sync with it.

Then sanity-check before starting anything:

```bash
bash scripts/check-env.sh     # required keys, provider names, no tracked secrets
bash scripts/check-ports.sh   # is REDIS_PORT actually free? (Windows: scripts\check-ports.ps1)
```
The port script reports *which* container/process holds a busy port and tells
you to bump `REDIS_PORT` in `.env` — it never suggests stopping anything that
belongs to another project.

Key settings in `.env`:

| Var | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `ollama` | `ollama`, `openai`, or `anthropic` |
| `LLM_MODEL` | `llama3.2` | Model name for the chosen provider |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama daemon |
| `REDIS_PORT` | `6380` | Host port for the compose Redis (never assume 6379) |
| `REDIS_URL` | `redis://localhost:6380/0` | Job queue — keep in sync with `REDIS_PORT` |
| `DATABASE_URL` | *(empty)* | Force an engine. Empty = MySQL, then SQLite fallback |
| `ALLOW_SQLITE_FALLBACK` | `true` | `false` = refuse to start without MySQL |
| `RATE_LIMIT_PER_MINUTE` | `10` | POST /forecasts budget per API key |
| `RATE_LIMIT_GET_PER_MINUTE` | `120` | Status-poll budget per API key |

## 2. Start the supporting services

```bash
# Redis — the job queue. docker-compose is the ONLY supported way to start
# dependencies: manual `docker run` creates untracked containers that compose
# can't see or update, which causes port/name confusion later.
docker compose up -d redis

# Ollama models (first time only; ~2.3 GB)
ollama pull llama3.2
ollama pull nomic-embed-text
```

The compose Redis container is named `forecastgpt-redis` and publishes
`${REDIS_PORT:-6380} -> 6379`. Verify: `docker ps --filter name=forecastgpt-redis`.

Ollama itself runs as a background app (it auto-starts on Windows). Verify:
`curl http://localhost:11434/api/tags`

## 3. Create a user + API key

```bash
python -m app.cli user create --email you@example.com --password your-secret
python -m app.cli key create --email you@example.com --password your-secret
# → prints an fgpt_... key ONCE. Save it; it cannot be shown again.
```

## 3b. (Optional) Console login via Supabase

The web console supports two ways in: API keys (above) or Supabase Auth
(email + Google OAuth). To enable login:

1. Create a free project at [supabase.com](https://supabase.com).
2. Root `.env`: set `SUPABASE_URL` to the Project URL (Settings → API).
   Session tokens are verified against the project's **public JWKS**
   (`<SUPABASE_URL>/auth/v1/.well-known/jwks.json`) — no secret needed on
   current projects. `SUPABASE_JWT_SECRET` is only for legacy projects still
   signing with the old symmetric secret.
3. `web/.env` (copy `web/.env.example`): set `VITE_SUPABASE_URL` and
   `VITE_SUPABASE_ANON_KEY` (anon public key from Settings → API).
4. Google sign-in: Supabase → Authentication → Providers → Google → enable,
   with an OAuth client from Google Cloud Console (redirect URI:
   `https://<project-ref>.supabase.co/auth/v1/callback`), and add your app
   URL under Authentication → URL Configuration.

Without this, everything still works in API-key mode.

## 4. Start the app (3 processes, 3 terminals)

```bash
# Terminal 1 — worker (executes forecasts)
export REDIS_URL=redis://localhost:6380/0        # match REDIS_PORT in .env
python -m app.worker

# Terminal 2 — API + web console
export REDIS_URL=redis://localhost:6380/0
uvicorn app.main:app --reload

# Terminal 3 (optional) — frontend live-reload during development
cd web && npm install && npm run dev             # http://localhost:5173
```

Open **http://localhost:8000** — the landing page and console are served by
FastAPI itself (from `web/dist`, rebuilt via `cd web && npm run build`).

## 5. Verify it end-to-end

1. Landing page shows live stats (`GET /stats`).
2. Click **See a live sample** — instant bundled forecast, no key needed.
3. Paste your `fgpt_…` key, pick a company, **Generate forecast**.
4. Watch the timeline (queued → running → completed, ~4–6 min on CPU).
5. The results view shows the metric chart, confidence gauge, and themes;
   the history panel (right) lets you reopen past forecasts.
6. API sanity check:

```bash
curl -X POST http://localhost:8000/forecasts \
  -H "X-API-Key: fgpt_..." -H "Content-Type: application/json" \
  -d '{"company": "TCS", "query": "Outlook for next quarter"}'
```

## 6. Tests & lint

```bash
pytest        # 78 tests, fully offline (no LLM/Redis/network needed)
ruff check .  # lint
```

## 7. Docker (alternative to step 2–4)

```bash
docker compose up --build api worker        # redis included; --profile mysql adds MySQL
```

---

## Going live — free options

### The LLM question (Ollama vs cloud)

Ollama runs **on your machine** — a deployed server usually has no GPU and no
Ollama daemon, so the local model simply won't be reachable there. This is
exactly why the provider abstraction exists: switching is **env-only**. The
recommended free cloud path is Google AI Studio (free key, no credit card)
via its OpenAI-compatible endpoint:

```env
LLM_PROVIDER=openai
EMBEDDING_PROVIDER=openai
OPENAI_API_KEY=<key from aistudio.google.com>
OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/
LLM_MODEL=gemini-2.0-flash-lite
EMBEDDING_MODEL=text-embedding-004
```

Groq (free, fast llama models) also works with `OPENAI_BASE_URL=https://api.groq.com/openai/v1`
for chat — but Groq has no embeddings endpoint, so pair it with another
embedding source. Gemini covers both chat and embeddings in one free key.

### Hosting

| Option | Free tier | Fits | Notes |
|---|---|---|---|
| **Oracle Cloud Always Free** (recommended) | 4-ARM-CPU / 24 GB RAM VM, forever | Whole stack | Needs a card for identity check. `docker compose up` runs redis + mysql + worker + api exactly as in the repo. |
| **Hugging Face Spaces** (easiest) | 2 vCPU / 16 GB, Docker, no card | Demo | Single container can run redis+worker+uvicorn. Storage is ephemeral (logs reset), sleeps after 48 h idle. |
| Render free | Web service only, no card | API + frontend | Background workers are **paid** — you'd still need a worker host. |
| Railway / Fly.io | Trial credit only | — | No longer free. |

### Database

- Demo: keep the SQLite fallback (logs are disposable).
- Real: **Aiven free MySQL** or **Neon free Postgres** (set `DATABASE_URL`;
  SQLAlchemy handles either). On the Oracle VM, just run the `mysql` profile.

### Checklist to go live

1. Push the repo (see CONTEXT.md / final commits).
2. Provision host + Redis + DB, set env vars (never commit real keys).
3. `docker compose up --build api worker` (or the host's equivalent).
4. Create the first user/key against the live DB:
   `docker compose exec api python -m app.cli user create ...`
5. Point at the cloud LLM env vars (above) — verify `GET /ready` is green.
6. Optional: put Cloudflare (free) in front for TLS + caching.
