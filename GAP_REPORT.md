# GAP_REPORT — Part A hardening & Part C productization audit

**Audited:** 2026-09-09 · branch `chore/ci-and-gap-report` · base `6345e91` (PR #1 merged)
**Phase 2 verification:** 2026-09-09 · branch `chore/verify-gap-findings` · base `31c3242` (PR #2 merged) — see the results section at the bottom.
**Scope:** the roadmap doc's Part A (environment hardening) and Part C
(strategic decisions C1–C5), plus anything found along the way.
**Method:** every finding below cites file/line evidence gathered from the
actual tree; Phase 2 re-verified each one independently before any fix
work starts.

---

## Summary

| Area | Status (updated 2026-09-12, after PR #8–#11) |
|---|---|
| A1 Redis port isolation | ✅ done (PR #1) — follow-ups GAP-06/GAP-07 **done** (PRs #6/#7 + #11) |
| A2 Requirements split | ✅ done (PR #1) |
| A3 Secrets hygiene | ✅ done (PR #1) — GAP-04 **done** (PR #7) |
| C1 Supabase Auth | ✅ **done** (PR #8): Supabase login (email+Google), JWKS verification (ES256/RS256 via PR #10), owner-scoped jobs |
| C2 Key/cost model | ✅ **resolved: hybrid implemented** (PR #8) — per-user + global daily quotas, BYOK via X-Provider-Key |
| C3 Custom company upload | ⏳ designed (GAP-03/05 + D-3); superseded in part by D-6 visual RAG — dedicated project |
| C4 "Report, not dashboard" positioning | ✅ **done** (PRs #9/#11): README + landing copy |
| C5 Free-tier deploy stack | ✅ documented (docs/DEPLOY.md, PR #9); execution = deployment step |
| D-6 Visual RAG (ColPali) | 📐 designed (this branch); dedicated project after launch |

Severity legend: **P0** breaks dev/deploy today · **P1** blocks a roadmap
phase · **P2** quality/positioning, no immediate breakage.

---

## Findings

### GAP-01 · Auth is API-key-only; no user-facing login (C1) — **P1**
- **Evidence:** `app/main.py` protects `POST /forecasts`, `GET /forecasts*`
  via `require_api_key` (`app/auth.py`); no password/session/OAuth endpoint
  exists (`grep password app/main.py` → nothing). Users exist only so the
  CLI can issue keys.
- **Impact:** the web console asks every visitor to paste an `fgpt_…` key —
  acceptable for developers, hostile for casual product users. C1's Supabase
  Auth (email + Google OAuth) is the intended fix; it also brings the free
  Postgres that retires the MySQL→SQLite fallback path (`ALLOW_SQLITE_FALLBACK`,
  `app/db/mysql.py`).
- **Action:** Phase 5 (`feat/auth-and-key-model`) — only after C2 is confirmed.

### GAP-02 · Arbitrary URL fetch is an SSRF surface (hardening follow-up) — **P1**
- **Evidence:** `app/utils/fetcher.py:82` `fetch_given_urls(urls)` downloads
  any user-supplied URL server-side (`_download`, line 38) with no scheme
  allowlist, host allowlist, private-IP block, redirect cap, or size cap.
  Reachable via `POST /forecasts` (`financial_doc_urls` / `transcript_urls`).
- **Impact:** any API-key holder can make the server fetch internal
  addresses (`http://169.254.169.254/`, `http://localhost:…`). Low risk while
  the key model is closed, but it must be closed before C2's public free tier.
- **Action:** allowlist to screener.in/bseindia.com domains (or an explicit
  allowlist env), block private/loopback/link-local IPs, cap download size.

### GAP-03 · Extraction is regex-only; will not survive arbitrary uploads (C3) — **P1**
- **Evidence:** `app/tools/financial_extractor.py` — metric extraction is
  `re.search` over cleaned text (line 20); text extraction is pdfplumber.
  No `unstructured`, no layout/table awareness. The bare-number fallback
  (added in `c569706`) trades recall for false-positive risk on decks it
  wasn't tuned for.
- **Impact:** works for the curated NSE registry (verified live on TCS/INFY/
  WIPRO decks) but C3's "upload any investor deck / 10-K excerpt" would
  produce wrong or missing numbers silently.
- **Action:** table-aware pipeline (`unstructured` or pdfplumber table
  extraction) + validation guardrails before enabling uploads; per-user
  upload size/count caps.

### GAP-04 · compose does not pass `OPENAI_BASE_URL` or the rate-limit vars — **P0 (for the free-cloud deploy path)**
- **Evidence:** `docker-compose.yml` api/worker `environment:` blocks include
  `OPENAI_API_KEY` (lines 33, 54) and `ANTHROPIC_API_KEY` but **not**
  `OPENAI_BASE_URL` (added to the app in `819e033`) nor
  `RATE_LIMIT_PER_MINUTE` / `RATE_LIMIT_GET_PER_MINUTE`.
- **Impact:** the documented free cloud-LLM path (Gemini via
  `OPENAI_BASE_URL`) silently falls back to real OpenAI under compose, and
  rate limits are stuck at app defaults in deployments.
- **Action:** add the three env passthroughs to both services. (Trivial fix
  branch: `fix/compose-env-passthrough`.)

### GAP-05 · Company registry is hardcoded; no custom-company path (C3) — **P1**
- **Evidence:** `app/companies.py` `SEED_COMPANIES` — 10 fixed NSE names,
  seeded idempotently; `resolve_company` only matches that table.
- **Impact:** adding a company is a code change + redeploy. Fine for the
  curated catalog; blocks C3's "any ticker via lookup or upload".
- **Action:** ticker/name lookup service, then admin/CLI command to extend
  the registry, then user uploads (GAP-03 first).

### GAP-06 · compose `mysql` profile hardcodes host port 3306 — **P2**
- **Evidence:** `docker-compose.yml` mysql service `ports: - "3306:3306"`
  (no `${MYSQL_PORT:-3306}` equivalent to the Redis fix in PR #1).
- **Impact:** on machines where 3306 is taken (this work laptop publishes
  its other MySQL on **3307**, so 3306 is currently free — but that is
  luck, not design), enabling the profile collides. Same bug class A1
  fixed for Redis.
- **Action:** `ports: ["${MYSQL_HOST_PORT:-3306}:3306"]` + README note.

### GAP-07 · `scripts/check-ports.sh|.ps1` only checks REDIS_PORT — **P2**
- **Evidence:** both scripts validate a single port (Redis). The MySQL
  profile port and the API's own 8000 are unchecked.
- **Impact:** incomplete coverage of exactly the collision class A1 was
  written to prevent.
- **Action:** extend the scripts to check API port and (when the mysql
  profile is enabled) the MySQL host port.

### GAP-08 · Positioning still "agent/dashboard", not "report, not dashboard" (C4) — **P2**
- **Evidence:** README title/intro ("AI-Powered Financial Outlook Agent"),
  landing hero copy in `web/src/components/Landing.tsx`.
- **Action:** Phase 6 (`docs/productization`) rewrites positioning around
  "a narrative outlook report per company — not another dashboard", and
  adds the competitive one-liner vs AlphaSense/Hebbia (institutional,
  contract-based) and Seeking Alpha/Simply Wall St/Koyfin (ratings, not
  narrative reports).

### GAP-09 · Deployment = self-host compose only (C5) — **P1 (after auth/key model)**
- **Evidence:** repo ships `Dockerfile` + `docker-compose.yml` for
  self-hosting; no Vercel/Render/Upstash/Supabase-Neon configuration,
  no `docs/DEPLOY.md`.
- **Action:** Phase 6 writes `docs/DEPLOY.md` for the C5 stack (Vercel
  frontend, Render backend, Upstash Redis, Supabase/Neon Postgres) with
  free-tier limits called out explicitly.

### GAP-10 · CI lacks a compose-build sanity check — **P1** → **fixed in this phase**
- **Evidence:** CI had lint+test+web jobs but never built the shipped
  image; a broken Dockerfile would only surface at deploy time.
- **Action:** added `compose-build` job (validate + build api/worker) in
  this branch. Note: CI lints with **ruff** (pyproject-configured; supersedes
  flake8's rule set) — black/flake8 were rejected to avoid a whole-repo
  reformat with no gain. Recorded as a deliberate deviation from the doc.

---

## Deviations & stale premises in the source doc (for the record)

1. CI already existed before Phase 1 (ruff + pytest + web build, from commit
   `a749a3c`) — Phase 1 only *added* the compose job.
2. Lint stack is ruff, not black+flake8 (decision above).
3. The MySQL→SQLite fallback is already loud/stamped (`ALLOW_SQLITE_FALLBACK`,
   `storage_backend` column) — C1's "replaces the silent fallback" note was
   written against the pre-Phase-0 code.
4. C2 remains **pending Abhay**: recommendation on record is the hybrid
   (small managed free quota bounded inside Gemini's free tier + BYOK for
   unlimited use). Phase 5 is blocked on this decision.

---

## Suggested fix order (to be prioritized in Phase 3)

1. **Now:** GAP-04 (compose env passthrough — tiny, unblocks free-cloud deploys), GAP-06/GAP-07 (port hygiene completion).
2. **With C2 decision:** GAP-01 + key model (Phase 5), then GAP-02 (SSRF) before any public key distribution.
3. **Product phase:** GAP-03 + GAP-05 (upload pipeline), GAP-08 (positioning), GAP-09 (DEPLOY.md).

---

## Phase 2 — Verification results (2026-09-09, `chore/verify-gap-findings`)

Every finding was re-checked against the merged tree (`31c3242`) with fresh
evidence; the two behavioral ones (GAP-02, GAP-03) were verified **live** by
running the stack, not just by reading code.

| ID | Verdict | Evidence on re-check |
|---|---|---|
| GAP-01 | ✅ VERIFIED | Only `require_api_key` guards forecast routes; no login/session/OAuth endpoint exists anywhere in `app/` (greps for login/session/oauth hit nothing but SQLAlchemy's `Session` class) |
| GAP-02 | ✅ VERIFIED — **live** | Ran api+worker against compose Redis; submitted a forecast with `financial_doc_urls=["http://127.0.0.1:9/ssrf-probe"]`. The worker made the outbound request to the internal loopback address (`HTTPConnectionPool(host='127.0.0.1', port=9)` in job #9's error) — no scheme/host/IP validation whatsoever |
| GAP-03 | ✅ VERIFIED — **live, worse than reported** | Fed the extractor USD-style filing text ("Total revenues were $4,913 million … operating margin was 21.4 percent"): it returned `total_revenue_inr_cr='4,913'` — **mislabeling millions as ₹ crore**: $4,913M is ≈ ₹40,800 crore at ₹83/$, so the reported figure understates the true value by roughly **8×** — and it missed profit and margin entirely. Arbitrary uploads would produce confidently wrong numbers, not just misses. Raises the priority of unit-awareness in the C3 pipeline |
| GAP-04 | ✅ VERIFIED | `OPENAI_BASE_URL` / `RATE_LIMIT_*` absent from `docker-compose.yml` **and** from the resolved `docker compose config` output |
| GAP-05 | ✅ VERIFIED | `SEED_COMPANIES` = exactly 10 symbols (TCS, INFY, HCLTECH, WIPRO, HDFCBANK, ICICIBANK, SBIN, RELIANCE, ITC, LT); no company-creation endpoint or CLI command exists |
| GAP-06 | ✅ VERIFIED | mysql service `ports: - "3306:3306"` hardcoded, no `${...}` indirection (unlike the Redis service) |
| GAP-07 | ✅ VERIFIED | Both scripts branch on a single port sourced from `REDIS_PORT` only; no API/MySQL port checks |
| GAP-08 | ✅ VERIFIED | README still titled "AI-Powered Financial Outlook Agent"; "report, not dashboard" appears nowhere in README or `web/src/components/Landing.tsx` |
| GAP-09 | ✅ VERIFIED | `docs/` contains only `how_to_run.md` (+ local CONTEXT.md); no `DEPLOY.md` |
| GAP-10 | ✅ VERIFIED (already fixed) | `compose-build` job present at `.github/workflows/ci.yml:51` building api+worker |

**Corrections to the original report:** none — all ten findings held up.
One severity amendment: **GAP-03 upgraded** from "wrong or missing numbers"
to "wrong numbers presented with confidence" (unit confusion), so the C3
extraction pipeline must include unit/currency normalization and sanity
bounds, not just table-aware parsing. **GAP-02's SSRF proof also upgrades
urgency**: it is reachable today by any API-key holder, so it should ship
with (or before) Phase 5's key distribution, not after.
