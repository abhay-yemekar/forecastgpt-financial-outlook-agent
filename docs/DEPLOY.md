# DEPLOY — putting ForecastGPT live on free tiers

Target stack (decision D-5 in `docs/PRODUCT_DECISIONS.md`):

| Piece | Service | Free tier |
|---|---|---|
| Frontend (web console) | **Vercel** (Hobby) | 100 GB bandwidth/mo, no card |
| API (FastAPI, serves `/forecasts` + auth) | **Render** (free web service) | 750 instance-hours/mo, spins down when idle |
| Worker (RQ, runs the forecasts) | **Fly.io** *or* an **Oracle Cloud Always-Free VM** | Fly ≈ $2–3/mo (no true free VM anymore); Oracle's ARM VM is free forever |
| Redis (job queue + rate limits + quota) | **Upstash** (free) | 10k commands/day, 256 MB |
| Postgres (optional: auth DB lives here already; app logs can too) | **Supabase** (free) — you already created this in Phase 5 | 500 MB, pauses after ~1 week of inactivity |
| LLM | **Google AI Studio** key (Gemini, OpenAI-compatible endpoint) | free tier, no card |

> Everything below works without a credit card **except** Fly.io (which needs
> one on file) — hence the Oracle alternative for the worker.

---

## 0. Free-tier limits you must design around (explicitly)

| Limit | Consequence | Mitigation used here |
|---|---|---|
| Render free web services **sleep** after ~15 min idle; cold start ≈ 30–60 s | First API request after idle is slow | Acceptable for a portfolio product; the console shows skeletons. Upgrading to Render Starter ($7/mo) removes it |
| **Render background workers are NOT free** | The RQ worker can't live on Render free | Put the worker on Fly.io, an Oracle Always-Free VM, or any $5 VPS — or use the single-container option in §5 |
| Upstash free = **10k commands/day** | A 3 s poller burns ~1.7k cmds/hour/user | Poll every 10 s from deployed frontend (`POLL_MS` in `web/src/App.tsx`); the bursty quota/ratelimit counters add only a handful per forecast |
| Supabase free projects **pause after ~1 week of no API traffic** | Logins fail while paused | Any periodic traffic unpauseues it; or restore manually from the dashboard |
| Gemini free tier ≈ 1,500 chat req/day | Cost ceiling for the managed key | Already enforced by the app: `QUOTA_FREE_PER_DAY` + `QUOTA_GLOBAL_PER_DAY` |
| Vercel Hobby is for **non-commercial** use | Fine for a portfolio/flagship demo | — |

---

## 1. Prerequisites (one-time, ~20 min)

1. **Accounts:** Vercel, Render, Upstash — all sign-up-able with GitHub. Fly.io or Oracle if you self-host the worker.
2. **Google AI Studio key:** [aistudio.google.com](https://aistudio.google.com) → Get API key. This is your *managed* LLM key (the one free-quota users consume).
3. **Supabase project:** done in Phase 5. You need from **Project Settings → API**:
   - `Project URL`
   - `anon public` key
   - `JWT Secret` (Settings → API → JWT Settings / "Legacy API keys")
   - For app *logs* in Postgres (optional): the connection string from **Project Settings → Database → Connection string → URI** (use the **connection pooler** on port `6543` for serverless/PaaS, and percent-encode the password).

## 2. Redis — Upstash

1. Upstash console → **Create database** → any region near your API region (e.g. `ap-south-1`), **Eviction: on**.
2. Copy the **REST**-less plain Redis endpoint: Upstash console → *Connect → Redis protocol* — you want the `rediss://default:<password>@<host>:6379` URL.
3. `REDIS_URL` = that URL everywhere below (note the `s` — Upstash requires TLS).

## 3. API — Render (free web service)

1. Render dashboard → **New → Web Service** → connect this GitHub repo.
2. Runtime: **Docker** (the repo's `Dockerfile` builds api + frontend; Render detects it).
3. Instance: **Free**.
4. Environment variables (Render → Environment):

| Var | Value |
|---|---|
| `REDIS_URL` | your Upstash `rediss://…` URL |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `openai` / `openai` |
| `OPENAI_API_KEY` | your Google AI Studio key |
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `LLM_MODEL` | `gemini-2.0-flash-lite` |
| `EMBEDDING_MODEL` | `text-embedding-004` |
| `SUPABASE_URL` / `SUPABASE_JWT_SECRET` | from Phase 5 (console login) |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_GET_PER_MINUTE` | `10` / `120` |
| `QUOTA_FREE_PER_DAY` / `QUOTA_GLOBAL_PER_DAY` | `3` / `400` |
| `ALLOWED_DOC_HOSTS` | leave unset (defaults cover screener/bse/nse) |
| `DATABASE_URL` | *(optional)* the Supabase Postgres pooler URI, if you want logs in Postgres. Omit → SQLite fallback (loud, stamped rows; ephemeral on Render — logs reset on redeploy) |

5. Health check path: `/health`. Deploy. Verify `https://<service>.onrender.com/ready` → `{"database":"ok","redis":"ok"}`.

## 4. Worker — the one piece Render free won't host

Pick one:

**Option A — Fly.io (simplest real option, ~$2–3/mo):**
```bash
fly launch --image <your-registry>/forecastgpt:latest   # or fly deploy after `docker build`
fly secrets set REDIS_URL=... LLM_PROVIDER=openai OPENAI_API_KEY=... \
  OPENAI_BASE_URL=... LLM_MODEL=gemini-2.0-flash-lite EMBEDDING_MODEL=text-embedding-004
fly scale count 1
# override the start command to run the worker:
#   fly.toml → [processes] worker = "python -m app.worker"  → fly deploy
```

**Option B — Oracle Cloud Always-Free VM (free forever, needs a card for identity):**
```bash
ssh ubuntu@<vm-ip>
git clone https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent
cd forecastgpt-financial-outlook-agent
docker compose up -d redis            # VM-local Redis is fine too
REDIS_URL=redis://localhost:6379/0 ... docker compose up -d worker
```
(Then optionally point the Render API at the same Upstash Redis — worker and API just need to share `REDIS_URL`.)

**Option C — same single container runs everything (demo-only):** skip Render; on any Docker host run one container whose command is `sh -c "redis-server & python -m app.worker & uvicorn app.main:app --host 0.0.0.0 --port $PORT"`. Works on Hugging Face Spaces (free, no card, ephemeral disk).

## 5. Frontend — Vercel

1. Vercel → **Add New → Project** → import the repo.
2. **Root Directory:** `web` · Framework: **Vite** (auto-detected).
3. Environment variables:
   - `VITE_SUPABASE_URL` / `VITE_SUPABASE_ANON_KEY` — your Supabase values.
4. Deploy. In Supabase → **Authentication → URL Configuration**: set *Site URL* to the Vercel URL and add `https://<app>.vercel.app/**` to redirect URLs (Google OAuth login redirects here).
5. The console talks to the API cross-origin: add the Vercel URL to CORS on the API (add `allow_origins` to the FastAPI CORS middleware — a one-line follow-up if you deploy split like this), **or** skip Vercel entirely and let Render serve the built frontend at the API's own origin (the repo already mounts `web/dist` — Option "single origin" needs no CORS at all).

> **Simplest first deployment:** set the API service on Render to run
> `npm run build`-output included (it is — the Dockerfile builds the web
> frontend), skip Vercel, and share the Render URL. Add Vercel later when
> you want a separate edge-hosted frontend.

## 6. First-run checklist (production)

```bash
# 1. first user + API key (run once against the production DB)
docker run --rm -e DATABASE_URL=<prod-url> <api-image> python -m app.cli user create --email you@... --password ...
docker run --rm -e DATABASE_URL=<prod-url> <api-image> python -m app.cli key create --email you@... --password ...

# 2. verify
curl https://<api>/health          # {"status":"ok"}
curl https://<api>/ready           # database+redis ok
curl https://<api>/stats           # live counts

# 3. submit a real forecast via API and watch it complete end-to-end
```

Project is "live and successful" when: the public URL serves the landing +
sample, a Supabase login works, and a keyed forecast completes on the host.
Update `docs/CONTEXT.md` § 6 with the URL afterwards.
