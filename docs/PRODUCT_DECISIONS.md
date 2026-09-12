# PRODUCT_DECISIONS — ForecastGPT strategy record

**Status:** living decision record · created 2026-09-09 (`docs/prioritization` phase)
**Inputs:** `GAP_REPORT.md` (10 findings, all verified in Phase 2) · the
roadmap doc's Part C · live-verified behavior (SSRF probe, extraction probe).
**Rule:** anything marked **DECISION NEEDED — Abhay** is not the agent's call;
the agent implements only after it is resolved here.

---

## Part 1 — Decision records (roadmap Part C)

### D-1 (C1) · Authentication — **direction accepted, gated on D-2**
- **Decision:** adopt **Supabase Auth** (email + Google OAuth, free tier) for
  the web console; the public API keeps `X-API-Key` keys. Supabase's bundled
  Postgres also becomes the primary datastore (`DATABASE_URL`), retiring the
  SQLite-fallback path (`ALLOW_SQLITE_FALLBACK`, `app/db/mysql.py`) for
  deployments — that fallback is already loud/stamped, so this is a
  simplification, not a rescue.
- **Why:** free tier covers the product's scale; OAuth removes the single
  biggest friction point in the console (paste-an-`fgpt_`-key, see GAP-01);
  one vendor for auth + DB keeps the free-tier stack coherent.
- **Alternatives rejected:** Clerk (generous but auth-only — we'd still need
  a separate DB); building session auth ourselves (never survives a security
  review cheaply).
- **Scope note:** existing `users`/`api_keys` tables stay — Supabase identity
  *owns* keys, the API-key mechanism itself is unchanged. GAP-01.

### D-2 (C2) · API-key / cost model — **RESOLVED (2026-09-09): hybrid** ✅
Abhay confirmed the recommendation. Implemented in `feat/auth-and-key-model`:
- Console users (Supabase Auth): `QUOTA_FREE_PER_DAY` (default 3) forecasts/day
  on the operator's managed LLM key + `QUOTA_GLOBAL_PER_DAY` (default 400)
  service-wide cap — UTC fixed windows in Redis (`app/quota.py`), counters
  rolled back on rejection. 429 carries `Retry-After` + a BYOK hint.
- **BYOK:** `X-Provider-Key` header on `POST /forecasts` bypasses the
  per-user quota; the key travels via a short-lived Redis side-channel
  (never in RQ queue payloads, which are logged) and is consumed once by the
  worker. BYOK keys are for the deployment's configured provider (e.g. a
  Gemini key when `OPENAI_BASE_URL` points at Gemini).
- API-key principals: operator/dev-level — rate-limited but never quota'd.
- Console users see only their own jobs (`forecast_logs.owner_id`);
  API keys see all.
- Cost containment math (why hybrid is safe): Gemini free tier allows
  ~1,500 chat requests/day (flash-class). At 3/day/user, 100 active users ≈
  300 calls/day — well inside budget; the global cap is the hard backstop.

### D-3 (C3) · Custom company support — **accepted, phased**
- **Decision:** ticker/name lookup first (search across NSE universe, insert
  into the registry on demand); document upload **only after** a real
  extraction pipeline exists. Uploads accept 10-K excerpts / investor decks
  via `pdfplumber`-with-table-awareness or `unstructured`, capped per
  free-tier user (e.g. ≤10 files, ≤20 MB each).
- **Verified constraint (Phase 2):** GAP-03's live probe showed the current
  regex extractor mislabels "$4,913 million" as "4,913 ₹ crore" — the true
  figure is ≈ ₹40,800 crore at ₹83/$, an ~8× understatement with no error
  signal. The pipeline **must** include unit/currency normalization and
  sanity bounds (e.g. reject revenue jumps >10× between quarters unless a
  second document confirms) before any upload path goes live.
- **Today's reality:** curated registry of 10 NSE names, no creation path
  (GAP-05) — fine for the demo catalog, blocks C3 by design.

### D-4 (C4) · Competitive positioning — **accepted: "report, not dashboard"**
- **Decision:** lead all copy (README, landing hero, social) with: *a
  narrative outlook report per company, grounded in real filings — not
  another dashboard*.
- **The gap being claimed:** institutional tools (AlphaSense, Hebbia,
  Bloomberg AskB) are expensive and contract-gated; retail tools (Seeking
  Alpha, Simply Wall St, Stock Rover, Koyfin) are dashboards/ratings, not
  narrative reports. ForecastGPT occupies the narrow, near-zero-cost middle:
  generated analyst-style narrative, no sales process, no $20+/month
  subscription.
- **Scope:** README rewrite + landing copy — Phase 6 (`docs/productization`),
  GAP-08.

### D-5 (C5) · Deployment stack — **accepted (free tier), execution later**
- **Decision:** Frontend **Vercel** (or Netlify) · Backend **Render**
  (Fly.io fallback) · Redis **Upstash** (serverless, free tier — also
  eliminates the entire local-port-collision class of bug in production, per
  Part A's lesson) · DB **Supabase/Neon Postgres** free tier.
- **Free-tier limits to document explicitly in `docs/DEPLOY.md`** (Phase 6,
  GAP-09): Render web service sleeps after idle & spins down (first-request
  latency); **Render background workers are NOT free** — the RQ worker needs
  the Fly fallback, a cheap VPS, or an Oracle Cloud Always-Free VM (the
  current self-host compose answer); Upstash free tier ≈ 10k commands/day —
  a 3s poller per active user is ~1.4k cmds/hour, so poll interval must be
  5–10s on that tier; Supabase/Neon free DBs pause on inactivity.
- **Interim truth:** today's deployment story is the repo's own
  `docker compose` (works on any VM, incl. Oracle Always Free) — documented
  in `docs/how_to_run.md`.

---

## Part 2 — Prioritization

### P0 — breaks dev/deploy today (ship before anything else)
*Source: Part A follow-ups + compose defects found in the audit. All tiny.*

| # | Item | Why it's P0 | Gap | Fix branch |
|---|---|---|---|---|
| P0-1 | compose passes `OPENAI_BASE_URL` + `RATE_LIMIT_*` to api/worker | Free-cloud LLM path silently falls back to real OpenAI under compose; rate limits stuck at defaults | GAP-04 | `fix/compose-env-passthrough` |
| P0-2 | compose mysql profile: `${MYSQL_HOST_PORT:-3306}` | Same collision class Part A fixed for Redis; bites the moment someone enables `--profile mysql` | GAP-06 | same branch as P0-1 |
| P0-3 | check-ports scripts cover API port + (profile-gated) MySQL port | Port checker incomplete vs its own purpose | GAP-07 | `fix/check-ports-coverage` |
| P0-4 | *(personal, Abhay)* add `REDIS_PORT=6380` to local `.env` | `check-env.sh` fails until present | — | local file, not a commit |

### P1 — roadmap-critical (order matters)
| # | Item | Depends on | Gap |
|---|---|---|---|
| P1-1 | SSRF hardening of `fetch_given_urls` (domain allowlist, private-IP block, size cap) | ships with/before Phase 5 — any key distribution exposes it | GAP-02 |
| P1-2 | Phase 5: Supabase Auth (D-1) + key model (D-2) | **D-2 decision by Abhay** | GAP-01 |
| P1-3 | `docs/DEPLOY.md` for the D-5 stack with free-tier limits | after P1-2 (deploy needs auth+quota design) | GAP-09 |

### P2 — product-quality (after the product has users)
| # | Item | Depends on | Gap |
|---|---|---|---|
| P2-1 | Extraction pipeline v2 (table-aware + unit normalization + sanity bounds) — prerequisite for any upload | verified GAP-03 behavior | GAP-03 |
| P2-2 | Custom companies: ticker lookup → registry insert → uploads | P2-1 | GAP-05 |
| P2-3 | Positioning rewrite ("report, not dashboard") in README + landing | none; cheap win, bundle with Phase 6 | GAP-08 |
| P2-4 | C5 migration execution (Vercel/Render/Upstash/Neon accounts + wiring) | P1-3 | GAP-09 |

### Explicitly deferred
Forecast-vs-actual accuracy tracking, NIFTY-50 expansion, WebSocket push,
server-side result caching — candidates for post-v1 sessions; accuracy
tracking deserves its own design pass.

---

## Open questions for Abhay (blocking)

1. **D-2 key model** — hybrid recommended; Phase 5 is blocked. Yes/no?
2. If hybrid: confirm quota shape (proposal: 3 forecasts/user/day, global
   daily cap = Gemini free-tier budget, BYOK bypasses quotas).
3. Upload policy comfort (D-3): cap shape ≤10 files / ≤20 MB per free user?
