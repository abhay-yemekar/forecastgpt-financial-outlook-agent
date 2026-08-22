# ForecastGPT – AI-Powered Financial Outlook Agent

## 📌 Overview
ForecastGPT is an end-to-end AI system designed to analyze real quarterly financial reports and earnings call transcripts, extract key financial insights, and generate qualitative next-quarter forecasts using **Ollama + LLaMA models**, **FAISS-based RAG**, and **FastAPI**.  
Built with production-like architecture — featuring PDF processing, vector embeddings, local LLM inference, caching, and MySQL logging.

---

## 🎯 Scope
ForecastGPT currently supports **Indian listed companies with [screener.in](https://www.screener.in) coverage** — documents are discovered from each company's Screener page (quarterly results, fact sheets, earnings-call transcripts). The company set lives in a seeded registry (`app/companies.py`); call `GET /companies` for the current list.

Adding a company = one line in `SEED_COMPANIES` (NSE symbol + Screener slug). Global filings (SEC/EDGAR, etc.) are a **clear extension point**, not a hidden limitation: plugging in another document source means adding a fetcher alongside `app/utils/fetcher.py`.

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
PDFs → Extractor → Chunker → FAISS Index → LLM Agent → Forecast Output
```

### **2. Sequence Flow**
```
User Query → Load PDFs → Cache → Embed → FAISS Search → Generate Context → LLaMA Response → Return JSON
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
### ✔ MySQL Logging  
### ✔ Automatic Caching of PDFs  
### ✔ Clean JSON API Output  

---

## 📡 API Usage
### **Endpoint: `/forecast`**
Request example:
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

### 4️⃣ Install Ollama
https://ollama.com/download

### 5️⃣ Pull LLaMA model
```
ollama pull llama3.2
```

### 6️⃣ Start API
```
uvicorn app.main:app --reload
```

### 7️⃣ (Optional) Run tests & lint
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
    query TEXT,
    input_meta JSON,
    output_json JSON,
    model_used VARCHAR(128),
    storage_backend VARCHAR(32),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Fallback behaviour:** if MySQL is not reachable at startup and `ALLOW_SQLITE_FALLBACK=true`
(the default), the app logs a prominent warning and writes to a local SQLite file
(`forecastgpt_fallback.db`) instead — and every `forecast_logs` row is stamped with
`storage_backend='sqlite_fallback'` so the fallback is never invisible. Set
`ALLOW_SQLITE_FALLBACK=false` to make an unreachable MySQL abort startup instead.
See `.env.example` for all configuration options.

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
