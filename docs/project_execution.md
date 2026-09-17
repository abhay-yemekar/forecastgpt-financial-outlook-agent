# Project Execution Guide — ForecastGPT

From a fresh clone to a running product, **PowerShell-first** (Git Bash
alternatives included), with expected outputs and a full troubleshooting
matrix. Deployment lives in [`DEPLOY.md`](DEPLOY.md).

---

## TL;DR quick start

```powershell
# 1. env + deps (one time)
py -3.10 -m venv .venv; .\.venv\Scripts\Activate.ps1
pip install -r requirements-dev.txt
Copy-Item .env.example .env

# 2. dependencies (every session)
docker compose up -d redis
ollama pull llama3.2; ollama pull nomic-embed-text

# 3. run (three terminals, after activating the venv in each)
python -m app.worker
uvicorn app.main:app --reload
# web dev server (optional): cd web; npm install; npm run dev

# 4. verify
curl http://localhost:8000/ready   # {"database":"ok","redis":"ok"}
```

Open **http://localhost:8000** — landing, sample report, sign-in, console.

---

## 0. Prerequisites

| Tool | Version | Why | Check |
|---|---|---|---|
| Python | **3.10–3.12** (3.14 does NOT work — no faiss-cpu wheels) | backend | `py -0` |
| Docker Desktop | recent | Redis (job queue) | `docker --version` |
| Ollama | 0.3+ | free local LLM | `ollama --version` |
| Node + npm | 20+ | frontend build/dev | `node --version` |

---

## 1. Backend setup (one time)

```powershell
cd forecastgpt-financial-outlook-agent
py -3.10 -m venv .venv            # or: python -m venv .venv
.\.venv\Scripts\Activate.ps1      # Git Bash: source .venv/Scripts/activate
pip install -r requirements-dev.txt
```

**Expected:** a long install ending without errors; the prompt now shows
`(.venv)`.

> PowerShell execution-policy error on Activate.ps1? See T-01 below.

Copy the config template and sanity-check it:

```powershell
Copy-Item .env.example .env
bash scripts/check-env.sh         # or compare .env against the table below
```

| Var | Default | Meaning |
|---|---|---|
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `ollama` | `ollama` · `openai` · `anthropic` |
| `LLM_MODEL` | `llama3.2` | model name for the provider |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama daemon |
| `REDIS_PORT` | `6380` | host port for compose Redis — **never assume 6379** |
| `REDIS_URL` | `redis://localhost:6380/0` | keep in sync with `REDIS_PORT` |
| `SUPABASE_URL` | *(empty)* | enables console login via project JWKS (§3b) |
| `QUOTA_FREE_PER_DAY` | `3` | free daily forecasts per console user |
| `DATABASE_URL` | *(empty)* | force an engine; empty = MySQL → SQLite fallback |
| `ALLOW_SQLITE_FALLBACK` | `true` | `false` = refuse to start without MySQL |

## 2. Start dependencies

**Redis — docker compose is the ONLY supported way** (manual `docker run`
creates untracked containers that cause port/name confusion):

```powershell
docker compose up -d redis
docker ps --filter name=forecastgpt-redis    # STATUS "Up", PORTS 0.0.0.0:6380->6379
bash scripts/check-ports.sh                  # verifies all host ports are free
```

Models (first time only, ~2.3 GB):

```powershell
ollama pull llama3.2
ollama pull nomic-embed-text
ollama list                                   # both listed
```

## 3. Users and keys

```powershell
python -m app.cli user create --email you@example.com --password your-secret
python -m app.cli key create  --email you@example.com --password your-secret
# prints an fgpt_... key ONCE — copy it into the console (developer mode)
```

### 3b. (Optional) Console login via Supabase

1. Free project at [supabase.com](https://supabase.com).
2. Root `.env`: `SUPABASE_URL=<Project URL>`. Current projects sign tokens
   with asymmetric keys — the backend verifies them against the project's
   public JWKS automatically. (`SUPABASE_JWT_SECRET` only for legacy
   projects.)
3. `web\.env` (copy `web/.env.example`): `VITE_SUPABASE_URL`,
   `VITE_SUPABASE_ANON_KEY`.
4. Google sign-in: Supabase → Authentication → Providers → Google (OAuth
   client redirect: `https://<ref>.supabase.co/auth/v1/callback`), and add
   your app URL under Authentication → URL Configuration.

## 4. Run the app

Three terminals (activate the venv in each). **PowerShell sets env vars
differently than bash** — the #1 stumbling block:

```powershell
# Terminal 1 — worker
$env:REDIS_URL="redis://localhost:6380/0"; python -m app.worker
# → "Starting RQ ... Listening on forecasts"

# Terminal 2 — API + site
$env:REDIS_URL="redis://localhost:6380/0"; uvicorn app.main:app --reload
# → "Application startup complete" on http://127.0.0.1:8000
```

```bash
# Git Bash equivalents (export works here, NOT in PowerShell):
export REDIS_URL=redis://localhost:6380/0
python -m app.worker
uvicorn app.main:app --reload
```

Optional frontend live-reload (only while editing `web/`):

```powershell
cd web; npm install; npm run dev     # http://localhost:5173, proxies API paths
```

Production-mode frontend (what the API serves at `/`):

```powershell
cd web; npm run build                # writes web/dist — FastAPI serves it
```

## 5. Verify end-to-end

1. `curl http://localhost:8000/ready` → `{"database":"ok","redis":"ok"}`
2. Open http://localhost:8000 → landing renders with live counters
3. **See a live sample** → real completed TCS report, no key needed
4. Paste your `fgpt_...` key (or Supabase sign-in) → pick company →
   **Generate forecast** → timeline runs queued→running→completed (~4–6 min
   locally) → full report with charts
5. API sanity:

```powershell
curl.exe -X POST http://localhost:8000/forecasts -H "X-API-Key: fgpt_..." -H "Content-Type: application/json" -d '{\"company\":\"TCS\",\"query\":\"Outlook\"}'
# {"job_id":1,"status":"queued","poll":"/forecasts/1"}
```

## 6. Tests & lint

```powershell
pytest        # 118 tests, fully offline (no LLM/Redis/network needed)
ruff check .
```

## 7. Full docker stack (alternative to §2+§4)

```powershell
docker compose up --build api worker      # + redis; --profile mysql adds MySQL
```

---

# Troubleshooting matrix

Symptom → cause → fix. Search for the error text you're seeing.

### Setup errors

**T-01 · `...cannot be loaded because running scripts is disabled on this system`**
PowerShell blocks `Activate.ps1` by default.
Fix: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` once, then
re-activate. (Or use Git Bash: `source .venv/Scripts/activate`.)

**T-02 · `export : The term 'export' is not recognized...`**
`export VAR=...` is bash syntax — **PowerShell uses `$env:VAR="..."`** (see
§4). The bash prefix form `REDIS_URL=... python -m app.worker` fails the
same way in PowerShell — set `$env:REDIS_URL` first, then run the command.

**T-03 · `pip install` fails on `faiss-cpu` (no wheel / build error)**
Your Python is 3.13/3.14 — faiss-cpu ships wheels only up to 3.12.
Fix: `py -3.10 -m venv .venv` (or 3.11/3.12), recreate, reinstall.

**T-04 · `docker: error during connect ... dockerDesktopLinuxEngine`**
Docker Desktop isn't running.
Fix: start Docker Desktop, wait for the whale to steady, confirm
`docker ps` works, retry.

**T-05 · `port is already allocated` / address already in use**
Another service owns the host port. `bash scripts/check-ports.sh` prints
WHICH container/process holds it.
Fix: change **our** port — `REDIS_PORT`/`API_PORT`/`MYSQL_HOST_PORT` in
`.env` (keep `REDIS_URL` in sync) — never stop the other project's
container. Duplicate configured ports are detected and fail loudly too.

**T-06 · `check-env.sh` fails: `REDIS_PORT is not set`**
`.env` predates the variable. Add `REDIS_PORT=6380` and
`REDIS_URL=redis://localhost:6380/0` to `.env`.

### Runtime errors

**T-07 · Startup warning `MySQL not available ... Falling back to SQLite`**
Not an error — the designed fallback when MySQL isn't running; every log row
is stamped `storage_backend='sqlite_fallback'`. To use real MySQL:
`docker compose --profile mysql up -d` + set `MYSQL_*`. To refuse the
fallback: `ALLOW_SQLITE_FALLBACK=false`.

**T-08 · `redis.exceptions.ConnectionError: Error 10061 ... 6380`**
Compose Redis isn't up (or the port differs).
Fix: `docker compose up -d redis`; verify
`docker exec forecastgpt-redis redis-cli ping` → `PONG`; check `REDIS_URL`
matches `REDIS_PORT`.

**T-09 · Worker starts but jobs stay `queued` forever**
Worker and API aren't sharing the queue — `REDIS_URL` differs between the
two terminals (or one still points at 6379). Stop both, set
`$env:REDIS_URL="redis://localhost:6380/0"` in each, restart the worker
first. Also confirm the worker process is actually alive (see T-24).

**T-10 · `ollama._types.ResponseError: model 'llama3.2' not found`**
A different tag is pulled (`llama3.2:3b` shows in `ollama list`).
Fix: `ollama pull llama3.2` (instant — layers dedupe).

**T-11 · `RuntimeError: OPENAI_API_KEY is not set`**
`.env` selects `LLM_PROVIDER=openai` without a key. Either add the key
(free Gemini: AI Studio key +
`OPENAI_BASE_URL=https://generativelanguage.googleapis.com/v1beta/openai/`)
or switch back: `LLM_PROVIDER=ollama`.

**T-12 · Forecast fails with `not an allowed document source`**
`ALLOWED_DOC_HOSTS` is set in `.env`, restricting fetches to those hosts.
Unset allows any public https host. Remove the variable or add the host.

**T-13 · Forecast fails with `resolves to a non-public address`**
SSRF guardrails refusing private/loopback targets — by design. Documents
must come from publicly resolvable hosts.

**T-25 · `[WinError 10013] An attempt was made to access a socket in a way forbidden by its access permissions` (uvicorn start)**
Port 8000 is taken or blocked. Two causes, in order of likelihood:
1. Another process holds it (a previous uvicorn that never died, another
   project's server): `netstat -ano | findstr :8000` → note the PID →
   `taskkill /PID <pid> /F` (only if it's YOURS), or simply run on another
   port: `uvicorn app.main:app --port 8010`.
2. Windows reserved the port range (Hyper-V/WSL does this):
   `netsh interface ipv4 show excludedportrange protocol=tcp` — if 8000
   falls in a range, use another port, or as admin:
   `net stop winnat && net start winnat` (clears dynamic reservations).

**T-26 · `pip's dependency resolver ... langchain-openai X requires langchain-core ... incompatible`**
A manually-installed `langchain-openai` (e.g. 1.6.0 from the langchain 1.x
line) conflicts with the repo's pinned langchain 0.3.x stack.
Fix: `pip install "langchain-openai==0.2.14" "langchain-core==0.3.63" "langsmith==0.1.147"`
(the set pinned in requirements.txt — `pip check` must end with "No broken
requirements found"). Future installs from `requirements*.txt` stay coherent.

**T-14 · Forecast completes but metrics say "Not found in the retrieved filings"**
Some decks publish financials as images/charts with a sparse text layer
(e.g. WIPRO) — regex extraction cannot read drawn numbers. Known limitation;
the ColPali visual-RAG project (D-6 in PRODUCT_DECISIONS.md) addresses it.
Reports still generate from transcripts + market data.

**T-15 · `429 ... rate limit` / `daily free quota is used up`**
Rate limit: wait for `Retry-After` seconds. Daily quota: resets at midnight
UTC; use `X-Provider-Key` (BYOK) for unlimited runs. **Failed jobs are
auto-refunded** — check `/quota/me`.

**T-16 · Login 503 `Console login is not configured`**
`SUPABASE_URL` is empty in the **server's** environment. Set it in `.env`
and restart the server (§3b).

**T-17 · Login 401 `Invalid session token`**
Usually the frontend and backend point at different Supabase projects.
Verify backend `.env` `SUPABASE_URL` == frontend `VITE_SUPABASE_URL`. Also
check system clock (skew >60s breaks token validity).

**T-18 · Google sign-in loops or `redirect_uri_mismatch`**
Supabase → Authentication → URL Configuration: add your exact site origin
(`http://localhost:8000`, prod URL) to redirect URLs; the Google OAuth
client must list `https://<ref>.supabase.co/auth/v1/callback`.

**T-19 · `503 Job queue unavailable; is Redis running?`** (on submit)
The API lost Redis mid-run. Restart compose Redis, then the API process.

### Frontend/site errors

**T-20 · Site looks stale / new sections missing**
The API serves the **build** in `web/dist`. After pulling changes:
`cd web; npm install; npm run build`, then hard-refresh (Ctrl+F5).
Use `npm run dev` during development to avoid this.

**T-21 · Dev proxy errors at `localhost:5173` (ECONNREFUSED :8000)**
API not running, or on a non-default port — the vite proxy reads `API_PORT`
(default 8000): `$env:API_PORT="8010"; npm run dev`.

**T-22 · Login works but forecast submit 401s**
Developer-mode API key invalid/revoked (`python -m app.cli key list`), or a
stale key in localStorage — re-enter it in the form.

**T-23 · `forecastgpt_fallback.db` schema errors after pulling**
Columns were added; the old local DB predates them. It's disposable log
data: stop the server, `Remove-Item forecastgpt_fallback.db`, restart.

**T-24 · Everything was working, now nothing responds**
Check the three processes survived (uvicorn, worker, compose Redis) — closed
terminals or sleep can kill them silently:
`docker ps --filter name=forecastgpt-redis`, then restart per §4.

### Still stuck?

Capture the triad: `GET /ready` output, the worker terminal logs, and the
failing request/response. Contact: yemekarabhays@gmail.com or open a GitHub
issue with those attached.

---

## Appendix — email/domain notes

`forecastgpt.github.io` (GitHub Pages) is **static hosting only** — it can
mirror the marketing site but cannot run the FastAPI backend or host email
(GitHub provides no email service). Current zero-cost setup: the product
email on the site is the maintainer's Gmail (`yemekarabhays@gmail.com`);
Gmail plus-aliasing (`yemekarabhays+forecastgpt@gmail.com`) can filter
product mail for free. Upgrade path when desired: buy a domain
(~₹500–900/yr, e.g. `forecastgpt.dev` on Cloudflare) → Cloudflare
**Email Routing** (free) forwards `hello@forecastgpt.dev` → Gmail → point
the domain at the deployment.
