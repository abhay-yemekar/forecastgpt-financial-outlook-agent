# ForecastGPT — Quarterly Outlook Reports, Grounded in Real Filings

> **A report, not a dashboard.** Pick an Indian listed company and ForecastGPT
> reads its latest results decks and earnings calls, then writes a
> narrative, confidence-scored outlook for the next quarter — as a web
> console and a developer API.

## 📌 Overview
ForecastGPT is an end-to-end AI system designed to analyze real quarterly financial reports and earnings call transcripts, extract key financial insights, and generate qualitative next-quarter forecasts using **Ollama + LLaMA models**, **FAISS-based RAG**, and **FastAPI**.  
Built with production-like architecture — featuring PDF processing, vector embeddings, local LLM inference, caching, and MySQL logging.

**Where it sits:** institutional research tools (AlphaSense, Hebbia, Bloomberg
AskB) are expensive and contract-gated; retail platforms (Seeking Alpha,
Simply Wall St, Stock Rover, Koyfin) are dashboards and ratings — not
narrative analysis. ForecastGPT occupies the narrow, near-zero-cost middle:
**a generated analyst-style outlook report per company** — no sales process,
no $20+/month subscription.

> **A report, not a dashboard.** See [docs/](docs/) for setup, deployment, and product decisions.

---

## 🎯 Scope
ForecastGPT currently supports **Indian listed companies with [screener.in](https://www.screener.in) coverage** — documents are discovered from each company's Screener page (quarterly results, fact sheets, earnings-call transcripts). The company set lives in a seeded registry (`app/companies.py`); call `GET /companies` for the current list.

Adding a company = one line in `SEED_COMPANIES` (NSE symbol + Screener slug). Global filings (SEC/EDGAR, etc.) are a **clear extension point**, not a hidden limitation: plugging in another document source means adding a fetcher alongside `app/utils/fetcher.py`.

## 📦 Docs
- [`docs/how_to_run.md`](docs/how_to_run.md) — step-by-step setup from a fresh clone
- [`docs/DEPLOY.md`](docs/DEPLOY.md) — going live on free tiers (Vercel + Render + Upstash + Supabase), free-tier limits spelled out
- [`docs/PRODUCT_DECISIONS.md`](docs/PRODUCT_DECISIONS.md) — the strategy record (auth, key/cost model, positioning)

---

## 🧩 Problem Statement
Financial analysts spend hours manually:
- Reading quarterly financial PDFs  
- Extracting metrics (revenue, margins, YoY/ QoQ performance)  
- Understanding management commentary  
- Identifying risks & opportunities  
- Building qualitative forecasts  

This project **automates** the entire workflow using an AI agent powered by local models + structured RAG.

---

## 🚀 Tech Stack & Why It Was Used
### **1. FastAPI**
- High-performance API framework  
- Auto-generates Swagger UI  
- Excellent for ML-serving  

### **2. Ollama (LLaMA 3.2) — default, local & free**
- Run LLMs locally  
- No API costs  
- Fast inference on-device  
- The backend is **configurable** via `LLM_PROVIDER` / `EMBEDDING_PROVIDER` (`ollama`, `openai`, `anthropic`) — switching is an env-only change; see `app/ai/` and `.env.example`. A deployed instance should point at a cloud provider since most hosts have no GPU for Ollama.

### **3. FAISS**
- Used for similarity search  
- Enables RAG over large PDF text chunks  
- Super fast vector indexing  

### **4. PDFPlumber**
- Extract structured PDF data  
- Handles complex PDFs  

### **5. MySQL**
- Stores logs  
- Auditable AI output  
- Demonstrates enterprise patterns  

---

## 🏗 Architecture
### **1. System Overview**
```
POST /forecasts ──▶ create job row (queued) ──▶ RQ/Redis queue
                                                      │
GET /forecasts/{id} ◀── forecast_logs (status) ◀── RQ worker
        (poll)                  ▲                     │
                                └── fetch PDFs → extract → FAISS RAG → LLM → parse
```
The HTTP request returns **immediately** (202 + job id); clients poll `GET /forecasts/{job_id}` — a slow (multi-minute) forecast never blocks or times out the request.

### **2. Sequence Flow**
```
User Query → job queued → Load PDFs → Cache → Embed → FAISS Search → Generate Context → LLaMA Response → JSON stored → polled by client
```

### **3. RAG Flow (FAISS)**
```
Documents → Chunk → Embeddings → FAISS Index → Top-K Retrieval → Context Passed to Model
```

---

## 📁 Project Structure
```
app/
│── agent.py               # ForecastAgent: pipeline + system prompt + JSON parsing
│── main.py                # FastAPI entrypoint (/forecast, /health)
│── tools/
│   ├── financial_extractor.py  # PDF → metrics + quarter-over-quarter trends
│   ├── qualitative_rag.py      # FAISS RAG over earnings-call transcripts
│   └── market_data.py          # Yahoo Finance stock quote (v8 chart API)
│── db/
│   ├── mysql.py           # Engine with explicit, logged SQLite fallback
│   └── models.py          # forecast_logs table
└── utils/
    ├── fetcher.py         # Screener.in scraping + PDF cache
    ├── text.py            # Text cleanup helpers
    ├── config.py          # Env-driven settings
    └── logger.py
```

---

## 🧪 Features
### ✔ PDF Extraction  
### ✔ Transcript Parsing  
### ✔ Financial Trend Analysis  
### ✔ Risk & Opportunity Detection  
### ✔ Local-LLaMA Forecast Generation  
### ✔ Any Indian Listed Company (seeded registry)  
### ✔ Async Job Queue (Redis + RQ, poll-based)  
### ✔ MySQL Logging  
### ✔ Automatic Caching of PDFs  
### ✔ Clean JSON API Output  

---

## 📡 API Usage
### **Submit: `POST /forecasts`** → `202` immediately
```json
{
  "query": "Analyze financials and provide a qualitative forecast.",
  "company": "TCS",
  "financial_doc_urls": [
    "https://example.com/TCS_Q3_results.pdf"
  ],
  "transcript_urls": [
    "https://example.com/TCS_Q3_transcript.pdf"
  ]
}
```
- `company` (required): NSE symbol or screener.in slug, e.g. `"TCS"`, `"INFY"`. Unknown companies get a clear 404 — check `GET /companies` for the supported list.
- `financial_doc_urls` / `transcript_urls` (optional): supply your own PDFs; otherwise the latest documents are auto-discovered from screener.in.
- Response: `{"job_id": 1, "status": "queued", "poll": "/forecasts/1"}`.

### **Poll: `GET /forecasts/{job_id}`**
```json
{ "job_id": 1, "company": "TCS", "status": "completed", "created_at": "...", "result": { "...": "full forecast JSON" } }
```
`status` moves `queued → running → completed` (result attached) or `failed` (error attached). Poll every few seconds.

### **Health: `GET /health`** — liveness. **`GET /ready`** — checks DB and Redis connectivity (503 when either is down).

### **Authentication — two ways in**
1. **Console users (Supabase Auth):** email+password or Google OAuth in the web console. Free daily quota (`QUOTA_FREE_PER_DAY`, default 3) on the operator's managed LLM key, bounded by a service-wide daily cap (`QUOTA_GLOBAL_PER_DAY`, 400). Users see only their own forecasts.
2. **Developers (API keys):** `X-API-Key` via the CLI — rate-limited but never quota'd; sees all jobs (operator level).

**BYOK (bring your own key):** any caller can send `X-Provider-Key: <key>` on `POST /forecasts` to bypass the quota — the key is used once for that job and never stored or logged.

Manage API keys:
```bash
python -m app.cli user create --email you@example.com --password 'secret'
python -m app.cli key create --email you@example.com --password 'secret'   # prints the raw key once
python -m app.cli key list --email you@example.com
python -m app.cli key revoke --prefix fgpt_AbC123
```
Rate limits per caller: `RATE_LIMIT_PER_MINUTE` (POST, 10/min) and `RATE_LIMIT_GET_PER_MINUTE` (status reads, 120/min) — `429` responses carry `Retry-After`. To enable console login, create a free Supabase project and set `SUPABASE_URL` (backend) + `VITE_SUPABASE_URL`/`VITE_SUPABASE_ANON_KEY` (frontend, see `web/.env.example`) — session tokens are verified against the project's public JWKS, so no secret is needed on current Supabase projects. See `docs/how_to_run.md`.

```bash
curl -X POST http://localhost:8000/forecasts \
  -H "X-API-Key: fgpt_YOUR_KEY" -H "Content-Type: application/json" \
  -d '{"company": "TCS", "query": "Outlook for next quarter"}'
```

---

## 🧰 Installation & Setup
### 1️⃣ Clone repo
```
git clone <repo-url>
cd ForecastGPT
```

### 2️⃣ Create virtual env
```
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
```

### 3️⃣ Install dependencies
```
pip install -r requirements.txt
```
Dependencies are split: `requirements.txt` is the runtime set; `requirements-dev.txt` adds only test/lint tooling (pytest, httpx, ruff, fakeredis) and includes the runtime file.

### 4️⃣ Configure environment
```
cp .env.example .env   # then edit if needed
```
> **This project never assumes port 6379 is free.** Set `REDIS_PORT` in `.env` to any free port on your machine — checked-in default is **6380**, chosen specifically because 6379 is commonly already in use by other local services. Keep `REDIS_URL` in sync with it.

Before starting anything, sanity-check your setup:
```
bash scripts/check-env.sh     # required keys, provider names, no tracked secrets
bash scripts/check-ports.sh   # is REDIS_PORT actually free? (never touches other containers)
```
Windows: `powershell -ExecutionPolicy Bypass -File scripts/check-ports.ps1`

### 5️⃣ Install Ollama
https://ollama.com/download

### 6️⃣ Pull LLaMA model
```
ollama pull llama3.2
```

### 7️⃣ Start Redis + the worker + the API
```
docker compose up -d redis        # Redis for the job queue (only supported way — never `docker run`)
python -m app.worker              # RQ worker (terminal 1)
uvicorn app.main:app --reload     # API (terminal 2)
```
`REDIS_URL` (repo default `redis://localhost:6380/0`) points both processes at your Redis; it must match `REDIS_PORT`.

### 8️⃣ (Optional) Run tests & lint
```
pip install -r requirements-dev.txt
pytest
ruff check .
```

---

## 🗄 MySQL Setup
```sql
CREATE DATABASE forecastgpt;
USE forecastgpt;

CREATE TABLE forecast_logs (
    id INT AUTO_INCREMENT PRIMARY KEY,
    company VARCHAR(16),
    query TEXT,
    status VARCHAR(16) NOT NULL DEFAULT 'queued',
    error TEXT,
    input_meta JSON,
    output_json JSON,
    model_used VARCHAR(128) NOT NULL,
    storage_backend VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    INDEX idx_status (status),
    INDEX idx_company (company)
);
```
Note: the schema gained `company`, `status`, and `error` columns in recent phases — if you created the table earlier, drop and recreate it (it holds request logs only).

**Fallback behaviour:** if MySQL is not reachable at startup and `ALLOW_SQLITE_FALLBACK=true`
(the default), the app logs a prominent warning and writes to a local SQLite file
(`forecastgpt_fallback.db`) instead — and every `forecast_logs` row is stamped with
`storage_backend='sqlite_fallback'` so the fallback is never invisible. Set
`ALLOW_SQLITE_FALLBACK=false` to make an unreachable MySQL abort startup instead.
See `.env.example` for all configuration options.

---

## 🖥 Web Frontend
A minimal Vite + React + TypeScript app (in `web/`) that is **just another client of the public API** — company picker, query box, API key (stored only in your browser), live job polling, and a results view with the quarter-over-quarter metric chart.
```bash
cd web
npm install
npm run dev      # dev server on :5173, proxies /forecasts + /companies to :8000
npm run build    # outputs web/dist, which the FastAPI app serves automatically
```
When `web/dist` exists, `uvicorn app.main:app` serves the built frontend at `/` — one deployable unit.

---

## 🚢 Deployment
Everything ships as one image (`Dockerfile`, multi-stage: Node builds the frontend, Python serves app + frontend). The RQ worker uses the same image with a different command.

**Local full stack via Docker:**
```bash
docker compose up --build api worker          # + redis; add --profile mysql for MySQL
```

**PaaS (Railway / Render / Fly.io all work):**
- Deploy the `api` service (the Dockerfile), plus a `worker` service from the same image with command `python -m app.worker`.
- Add managed Redis and MySQL add-ons; point `REDIS_URL` and `DATABASE_URL` (or `MYSQL_*`) at them.
- Set `LLM_PROVIDER`/`EMBEDDING_PROVIDER` to a cloud provider (`openai`/`anthropic` + the matching API key) — most hosts have no GPU for Ollama. Ollama stays the local-dev default.
- Create your first user + API key by running the CLI once against the production DB, e.g. `docker run --rm <image> python -m app.cli user create ...`.

CI (`.github/workflows/ci.yml`) runs ruff + pytest and a frontend type-check/build on every push/PR.

---

## 🖼 Screenshots (Located in `/screenshots`)
1. Architecture diagram  
2. Sequence flow  
3. FAISS/RAG flow  
4. Swagger UI  
5. POST request demo  
6. MySQL log table  
7. Terminal running FastAPI  

---

## 🛡 GitHub Visibility Boosters
- Well-structured project directory  
- Clean `.gitignore`  
- Professional README  
- Architecture diagrams  
- Screenshots folder  
- LICENSE file  
- Tags for discoverability  

---

## 📜 License
MIT License

---

## 🎉 Author
**Abhay Yemekar**  
Python Developer | AI Engineer  
