# DEPLOY — putting ForecastGPT live (free tiers, step by step)

Same standard as [`project_execution.md`](project_execution.md): numbered
steps, expected outputs, and a troubleshooting matrix (D-01…D-14) at the
bottom. Read §0 and §1 first; **Path A is the recommended go-live** (100%
free, no credit card).

---

## 0. Pre-flight checklist — everything must be ✅ before starting

| # | Item | Status |
|---|---|---|
| 1 | All roadmap phases merged (main ≥ PR #15) | ✅ done |
| 2 | **Supabase project** created; `SUPABASE_URL` + `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` known | ✅ done (Phase 5) |
| 3 | **Google AI Studio key** — [aistudio.google.com](https://aistudio.google.com) → Get API key | ⬜ do now |
| 4 | **Upstash** account (sign in with GitHub) | ⬜ do now |
| 5 | **Render** account (sign in with GitHub) | ⬜ do now |
| 6 | Repo visible on your GitHub (it is) | ✅ |

Free-tier limits that shape every step (details in the matrix): Render free
**sleeps** after ~15 min idle (cold start 30–60 s) · Upstash free ≈ 10k
commands/day · Supabase pauses after ~1 week idle · Gemini free ≈ 1,500
chat req/day (the app's quotas already bound us inside this).

## 1. Upstash Redis (10 min)

1. console.upstash.com → **Create Database** → name `forecastgpt` → region
   `ap-south-1` (Mumbai, near Indian users) → **Eviction: ON** → Create.
2. Database page → **Connect → Redis Protocol** (NOT "REST API") → copy the
   URL. It looks like `rediss://default:<long-password>@<name>.upstash.io:6379`
   — note **rediss** (TLS is mandatory on Upstash).
3. No local verification needed — §3's `GET /ready` check is the real gate
   (it must show `"redis":"ok"`).

## 2. Render — ONE service runs everything (Path A, recommended)

We use the app's **embedded worker** (`EMBED_WORKER=1`): the API process
spawns its own RQ worker thread, so one free Render service hosts the
website, accepts submissions, AND executes forecasts. No Fly.io, no second
server, no CORS setup (site + API share one origin).

1. dashboard.render.com → **New + → Web Service** → **Build and deploy from
   a Git repository** → connect GitHub → pick
   `forecastgpt-financial-outlook-agent`.
2. Configuration:
   - **Language:** Docker (Render finds the repo `Dockerfile`)
   - **Instance type:** Free
   - **Health Check Path:** `/health`
3. **Environment → Add** all of these (values from your pre-flight):

| Var | Value |
|---|---|
| `EMBED_WORKER` | `1` |
| `REDIS_URL` | your `rediss://default:…@….upstash.io:6379` URL |
| `LLM_PROVIDER` / `EMBEDDING_PROVIDER` | `openai` / `openai` |
| `OPENAI_API_KEY` | AI Studio key |
| `OPENAI_BASE_URL` | `https://generativelanguage.googleapis.com/v1beta/openai/` |
| `LLM_MODEL` | `gemini-2.0-flash-lite` |
| `EMBEDDING_MODEL` | `text-embedding-004` |
| `SUPABASE_URL` | your Supabase Project URL |
| `QUOTA_FREE_PER_DAY` / `QUOTA_GLOBAL_PER_DAY` | `3` / `400` |
| `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_GET_PER_MINUTE` | `10` / `120` |
| `ALLOWED_DOC_HOSTS` | leave UNSET (companies host filings on their own domains) |
| `DATABASE_URL` | **Recommended for launch: omit entirely** — logs then use the SQLite fallback (ephemeral on Render; reset on redeploy). To keep durable logs in Supabase Postgres, see §2b below — the URI needs a small format change |

   **Expected:** first deploy builds the Docker image (Node builds the
   frontend inside it, then Python) — **5–10 minutes**. "Live" appears in the
   dashboard header with a `https://forecastgpt-xxxx.onrender.com` URL.
4. **Verify (gate):** open `https://<url>/ready`
   → `{"database":"ok","redis":"ok"}`. If redis says unavailable → D-02. If
   the service build failed → D-01.
5. Open the site root → landing renders with live counters → **See a live
   sample** works (no login).

## 3. Supabase — allow the new origin (5 min)

Supabase → **Authentication → URL Configuration**: set **Site URL** and add
`https://<your-render-url>` to **Redirect URLs**. Without this, Google
sign-in on the deployed site loops or errors (D-08).

**Verify (gate):** on the deployed site → Console → you are routed to the
sign-in page → **Continue with Google** → you land back signed in, the nav
shows your name and "N left today". If not → D-07/D-08.

## 4. Create the production API key (for developer access)

Console login needs nothing here, but for API access to production:

```powershell
# Render dashboard → your service → "Shell" tab:
python -m app.cli user create --email you@example.com --password <secret>
python -m app.cli key create --email you@example.com --password <secret>
# → fgpt_... printed ONCE — save it
```

*(No Shell on free tier? Use the Supabase Postgres `DATABASE_URL` route:
run the same CLI locally with that `DATABASE_URL` exported — the users/keys
tables then match production.)*

**Verify (gate):**
```powershell
curl.exe -X POST https://<url>/forecasts -H "X-API-Key: fgpt_..." -H "Content-Type: application/json" -d '{\"company\":\"TCS\",\"query\":\"Outlook for next quarter\"}'
# → 202 {"job_id":1,"status":"queued","poll":"/forecasts/1"}
```

## 5. End-to-end live gate (the definition of "live")

On the deployed site, signed in: pick **TCS** → **Generate forecast** →
timeline runs queued → running → **completed** in ~2–5 min (Gemini is fast)
→ full report with charts.

**"Live and successful" = all five true:**
- [ ] Public URL serves landing + interactive sample
- [ ] `/ready` → both checks ok
- [ ] Supabase sign-in works on the deployed origin
- [ ] A logged-in forecast completes end-to-end with charts
- [ ] `GET /stats` increments

Then update `docs/CONTEXT.md` §6 with the URL and date.

---

## Path B — split worker (production-ish, optional later)

When volume grows beyond one free instance: remove `EMBED_WORKER`, add a
dedicated worker service.

- **Fly.io (~$2–3/mo, card on file):** `fly launch --image` from the built
  image → `fly secrets set REDIS_URL=… …` → in `fly.toml` set the process
  command to `python -m app.worker` → `fly deploy`.
- **Oracle Cloud Always-Free VM (free forever, card for identity):** clone
  the repo on the VM → `docker compose up -d worker` with the same env vars
  (it shares the same Upstash `REDIS_URL` — worker and API only need to
  agree on Redis).
- **Hugging Face Spaces (₹0, no card):** import the repo as a Docker Space
  with `EMBED_WORKER=1` + env vars — same single-container mode as Path A.
  Ephemeral disk; fine for demos.

## Vercel frontend (optional, later)

The site already ships from the API origin — you don't need Vercel to be
live. If you want the separate edge-hosted frontend: import repo (Root
Directory `web`, framework Vite), set `VITE_*` env vars, then add the
Vercel URL to Supabase redirect URLs **and** enable CORS on the API
(`allow_origins` middleware — small code change). Skip until needed.

---

# Deploy troubleshooting matrix (D-01…D-14)

**D-01 · Render build fails (Node or pip stage)**
Read the failing line in Render's *Events* log. Most common: a new
dependency missing from `requirements.txt` (fix locally, push — Render
redeploys automatically on main). Frontend build errors: run `npm run build`
locally first; never push a broken `web/`.

**D-02 · `/ready` → `"redis":"unavailable"`**
- `REDIS_URL` must start with `rediss://` (TLS) for Upstash — `redis://`
  fails.
- Copy the **Redis Protocol** URL, not the REST one (REST URLs start
  `https://` and are a different protocol).
- Upstash → your DB → check the region isn't blocking; "Allowlist" must
  include Render's egress or be disabled (default).

**D-03 · `/ready` → `"database":"unavailable"`**
`DATABASE_URL` is malformed or unreachable. Checklist: scheme must be
`postgresql+psycopg2://` (not `postgresql://`); use the **pooler** host
(`…pooler.supabase.com:6543`), not `db.<ref>.supabase.co:5432` (IPv6-only);
password percent-encoded; driver `psycopg2-binary` ships in requirements
since PR #18. Or omit `DATABASE_URL` entirely → SQLite fallback for logs.

**D-04 · Site renders but every submit → `503 Job queue unavailable`**
The API lost Redis mid-run, or `EMBED_WORKER` was forgotten AND no external
worker exists: with one free Render service you MUST set `EMBED_WORKER=1`
(or run Path B's worker). Add the var → Render redeploys on save.

**D-05 · Forecast stuck at `running` for >10 minutes**
Free instances are CPU-starved; Gemini calls still usually finish in 2–5
min. Check Logs: if the LLM call errors (401/429 from Gemini), the job
fails and quota is refunded — the timeline will show it. Repeated 429 from
Gemini: you exhausted the AI Studio daily budget; wait or add your own key
via BYOK.

**D-06 · Cold start: first request takes 30–60 s, then it's fast**
Render free sleeps after ~15 min idle. That's the tier. Share the URL;
users hit the same warm-up once. Remove with Render Starter ($7/mo).

**D-07 · `503 Console login is not configured`** on the deployed site
`SUPABASE_URL` wasn't set (or the service wasn't redeployed after adding
it). Environment changes on Render trigger a redeploy — confirm the
"Deploy live" event finished after your edit.

**D-08 · Google sign-in loops / `redirect_uri_mismatch` / stuck on callback**
Supabase → Authentication → URL Configuration: Site URL + Redirect URLs
must include your **exact** deployed origin. The Google OAuth client (in
Google Cloud Console) must list `https://<ref>.supabase.co/auth/v1/callback`.

**D-09 · Login works locally but 401s deployed (or vice-versa)**
Frontend and backend point at different Supabase projects:
`VITE_SUPABASE_URL` (frontend build) must equal `SUPABASE_URL` (backend).
Remember `VITE_*` values are baked at **build time** — after changing them,
redeploy the service so `web/dist` is rebuilt.

**D-10 · Forecast fails: `not an allowed document source`**
`ALLOWED_DOC_HOSTS` was set on Render, restricting fetches. Default (unset)
allows any public https host — remove the variable.

**D-11 · Forecast fails: `resolves to a non-public address`**
SSRF guardrails working as designed — the URL points at private space.

**D-12 · `429 rate limit / daily free quota used up`**
Working as intended; failed jobs are auto-refunded, so check `/quota/me`.
Raise `QUOTA_*`/`RATE_LIMIT_*` on Render if you're the only user and hit
limits yourself.

**D-13 · Upstash `max requests limit exceeded` (HTTP 429 from Upstash)**
Free tier = 10k commands/day. Biggest consumers: status polling + the
embedded worker's queue polling. Polling at 3 s ≈ 1.7k cmds/hour/user —
switch `POLL_MS` to 10 000 in `web/src/App.tsx` for a deployed frontend
(~600/hour/user) or upgrade Upstash (pay-as-you-go pennies).

**D-15 · Deploy/runtime error `No module named 'langchain_core.messages.block_translators…'`**
Mixed langchain 1.x and 0.3.x packages in the environment (e.g. a manually
installed `langchain-openai` 1.x next to pinned 0.3.x). requirements.txt now
pins a coherent late-0.3 train — redeploy (Render rebuilds from main) or
run `pip install -r requirements.txt` locally. See T-27 for the local
recovery commands.

**D-14 · Supabase login suddenly 401s for everyone**
The free project **paused** after ~1 week without API traffic — restore it
in the Supabase dashboard (Restore project), and prevent recurrence with
any weekly traffic (the deployed site's sign-ins themselves count).

---

## After go-live

- Update `docs/CONTEXT.md` §6: URL, date, host.
- Watch the first week: Render Logs (worker + LLM errors), Upstash daily
  command count, Gemini quota in AI Studio.
- Then start the ColPali project (D-6) — the designed next phase.
