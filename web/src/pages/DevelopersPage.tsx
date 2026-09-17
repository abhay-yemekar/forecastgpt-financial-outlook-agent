import { CONTACT } from '../content/site'
import Reveal from '../components/Reveal'

const ENDPOINTS: [string, string, string][] = [
  ['POST', '/forecasts', 'Submit a forecast job. Returns 202 + job id immediately. Requires auth.'],
  ['GET', '/forecasts/{id}', 'Poll a job. status: queued → running → completed (result attached) or failed (error attached).'],
  ['GET', '/forecasts', 'Your recent jobs, newest first. Optional ?company=SYMBOL filter.'],
  ['GET', '/quota/me', 'Remaining free quota for console users. API keys: unlimited.'],
  ['GET', '/companies', 'Covered companies (open — no auth needed).'],
  ['GET', '/stats', 'Live counters for the landing page (open).'],
  ['GET', '/health', 'Liveness probe.'],
  ['GET', '/ready', 'Readiness: DB + Redis connectivity (503 when down).'],
]

const ERRORS: [string, string][] = [
  ['400', 'Malformed request body.'],
  ['401', 'Missing/invalid credentials. Pass X-API-Key or a Bearer session token.'],
  ['404', 'Unknown company or job id (also returned for jobs owned by another user).'],
  ['429', 'Rate limit or daily quota exhausted — honor the Retry-After header.'],
  ['503', 'Job queue (Redis) or session-verification backend unavailable.'],
]

function Copyable({ children }: { children: string }) {
  return (
    <div className="dev-code glass">
      <pre className="mono">{children}</pre>
    </div>
  )
}

export default function DevelopersPage() {
  return (
    <div className="page-narrow">
      <Reveal>
        <h1 className="page-title">
          Developer <span className="grad-text">API reference</span>
        </h1>
        <p className="muted" style={{ maxWidth: 640 }}>
          The console is just a client of this API. Submit a job, poll until it
          completes, get stable JSON. Auth works two ways: an API key (mint with
          the CLI) or a Supabase session token (console users).
        </p>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Authentication</h2>
        <Copyable>{`# Developer path — API key (mint via CLI)
python -m app.cli key create --email you@example.com --password your-secret
# → fgpt_... (shown once)

curl -H "X-API-Key: fgpt_..." https://your-host/forecasts

# Console-user path — Supabase session
curl -H "Authorization: Bearer <access_token>" https://your-host/forecasts

# Optional: bring your own provider key — bypasses the free quota
curl -H "X-Provider-Key: <your-key>" ...`}</Copyable>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Endpoints</h2>
        <div className="glass card ep-table">
          {ENDPOINTS.map(([method, path, desc]) => (
            <div className="ep-row" key={method + path}>
              <span className={`badge ${method === 'POST' ? 'down' : 'up'} mono`}>{method}</span>
              <code className="mono">{path}</code>
              <span className="muted small">{desc}</span>
            </div>
          ))}
        </div>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Submit → poll → result</h2>
        <Copyable>{`# 1. submit (returns immediately — the pipeline runs async)
POST /forecasts  {"company": "TCS", "query": "Outlook for next quarter"}
→ 202 {"job_id": 12, "status": "queued", "poll": "/forecasts/12"}

# 2. poll every few seconds
GET /forecasts/12  →  {"status": "running"}

# 3. done
GET /forecasts/12  →  {"status": "completed", "result": { ...report JSON... }}`}</Copyable>
        <p className="muted small">
          result carries company, period_analyzed, financial_trends,
          management_themes, risks, opportunities,
          qualitative_forecast_next_quarter, confidence, market_context and
          financial_metrics (raw quarter-over-quarter numbers for charting).
        </p>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Python & JavaScript</h2>
        <Copyable>{`# Python
import requests, time
H = {"X-API-Key": "fgpt_..."}
job = requests.post("https://your-host/forecasts", headers=H,
                    json={"company": "INFY", "query": "Outlook"}).json()
while True:
    d = requests.get(f"https://your-host/forecasts/{job['job_id']}", headers=H).json()
    if d["status"] in ("completed", "failed"): break
    time.sleep(5)
print(d.get("result", d))`}</Copyable>
        <Copyable>{`// JavaScript (browser / node)
const H = { "X-API-Key": "fgpt_..." };
const job = await fetch("/forecasts", { method: "POST", headers: H,
  body: JSON.stringify({ company: "INFY", query: "Outlook" }) }).then(r => r.json());
let d;
do { await new Promise(r => setTimeout(r, 5000));
     d = await fetch(\`/forecasts/\${job.job_id}\`, { headers: H }).then(r => r.json());
} while (!["completed", "failed"].includes(d.status));`}</Copyable>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Errors & limits</h2>
        <div className="glass card ep-table">
          {ERRORS.map(([code, desc]) => (
            <div className="ep-row" key={code}>
              <span className="badge down mono">{code}</span>
              <span className="muted small">{desc}</span>
            </div>
          ))}
        </div>
        <p className="muted small" style={{ marginTop: 10 }}>
          Rate limits per caller: 10 submissions/min and 120 status reads/min
          (429 carries <code>Retry-After</code>). Console users also get a free
          daily forecast quota (<code>QUOTA_FREE_PER_DAY</code>) — failed jobs
          are automatically refunded. Configure via environment; see{' '}
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent/blob/main/.env.example" target="_blank" rel="noreferrer">
            .env.example
          </a>
          .
        </p>
      </Reveal>

      <Reveal delay={80}>
        <h2 className="page-section">Self-hosting</h2>
        <p className="muted">
          The whole stack is open source: docker compose locally, or the
          free-tier deployment guide (Vercel + Render + Upstash + Supabase) in{' '}
          <a href={CONTACT.deployGuide} target="_blank" rel="noreferrer">
            docs/DEPLOY.md
          </a>
          . Report issues on{' '}
          <a href={CONTACT.repo} target="_blank" rel="noreferrer">
            GitHub
          </a>
          .
        </p>
      </Reveal>
    </div>
  )
}
