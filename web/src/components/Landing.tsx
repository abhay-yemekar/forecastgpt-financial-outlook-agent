import sampleJob from '../data/sampleResult.json'
import type { Stats } from '../types'
import { useCountUp } from '../useCountUp'
import Faq from './Faq'
import HeroMock from './HeroMock'
import MetricCard from './MetricCard'
import Reveal from './Reveal'

interface Props {
  stats: Stats | null
  onSample: () => void
  onLaunch: () => void
  onAuth: () => void
}

const PROBLEMS = [
  {
    icon: '⏱',
    title: 'Hours per company, every quarter',
    body: '80-page decks, dual-axis charts, footnoted percentages. Multiply by the ten names you track — that is your weekend.',
  },
  {
    icon: '📊',
    title: 'The numbers hide in charts',
    body: 'A margin trend drawn as a line graph, revenue inside a waterfall — invisible to keyword search and to generic chatbots.',
  },
  {
    icon: '🎯',
    title: 'Ratings are not reasoning',
    body: 'Screeners give you a score. You need the narrative: what management said, what changed quarter over quarter, and what it means next.',
  },
]

const SOLUTION_POINTS = [
  { icon: '◈', title: 'Grounded, with receipts', body: 'Every figure traces to a page of a real filing. Missing numbers stay missing — no confident hallucinations.' },
  { icon: '∑', title: 'Numbers actually computed', body: 'Quarter-over-quarter deltas are extracted and calculated, not paraphrased by a language model.' },
  { icon: '❖', title: 'Earnings-call RAG', body: 'FAISS retrieval over transcripts brings management’s own words into the analysis.' },
  { icon: '⧗', title: 'Minutes, not weekends', body: 'Async pipeline runs the whole job in the background. You get a structured report, not a blocked browser tab.' },
]

const STEPS = [
  { n: '01', title: 'Pick a company', body: 'Any covered NSE-listed name from the registry — TCS, Infosys, HDFC Bank, Reliance and more.' },
  { n: '02', title: 'Real filings, fetched', body: 'The pipeline discovers the latest results decks and earnings-call transcripts on screener.in and pulls them down.' },
  { n: '03', title: 'Metrics + RAG', body: 'Numbers are extracted and compared quarter over quarter; transcripts are embedded and retrieved per analytical theme.' },
  { n: '04', title: 'Narrative report', body: 'A structured, confidence-scored outlook — trends, themes, risks, opportunities — delivered as JSON and a readable view.' },
]

const FEATURES = [
  { icon: '◈', title: 'Grounded, not guessed', body: 'Every report cites the filings it was built from. If a metric isn’t in the documents, the report says so instead of inventing it.' },
  { icon: '❖', title: 'Earnings-call RAG', body: 'FAISS retrieval over transcripts surfaces management themes, guidance and risks in their own words.' },
  { icon: '⧗', title: 'Async by design', body: 'Redis + RQ job queue. Submissions return in milliseconds; poll until the report lands. Built for multi-minute reasoning.' },
  { icon: '⌘', title: 'API-first', body: 'The console uses the exact public contract: X-API-Key auth, per-key rate limits, stable JSON. Script it, ship it.' },
  { icon: '🔑', title: 'BYOK + fair quota', body: 'Sign in for free daily forecasts on us, or plug in your own provider key for unlimited runs — your key never touches our database.' },
  { icon: '⚙', title: 'Configurable brain', body: 'Ollama locally for free, Gemini/Groq/OpenAI/Anthropic in the cloud. Switching is an environment variable, not a rewrite.' },
]

const DEV_CURL = `curl -X POST https://your-host/forecasts \\
  -H "X-API-Key: fgpt_..." \\
  -H "Content-Type: application/json" \\
  -d '{"company": "TCS", "query": "Outlook for next quarter"}'

# → 202 Accepted
{"job_id": 12, "status": "queued", "poll": "/forecasts/12"}`

const DEV_JSON = `{
  "job_id": 12,
  "status": "completed",
  "result": {
    "company": "Tata Consultancy Services",
    "financial_trends": {
      "revenue": "stable, driven by digital revenues",
      "operating_margin": "down 5.1% QoQ"
    },
    "confidence": { "level": "medium" }
  }
}`

function StatTile({ label, value }: { label: string; value: number | null }) {
  const animated = useCountUp(value)
  return (
    <div className="glass hover-lift stat-tile">
      <strong className="mono">{value == null ? '—' : Math.round(animated).toLocaleString('en-IN')}</strong>
      <span className="muted small">{label}</span>
    </div>
  )
}

export default function Landing({ stats, onSample, onLaunch, onAuth }: Props) {
  const scrollTo = (id: string) => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
  void scrollTo

  return (
    <div className="landing">
      {/* ---------- 1. HERO ---------- */}
      <section className="hero" id="top">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
        <div className="hero-grid">
          <div className="hero-copy">
            <Reveal>
              <span className="chip hero-eyebrow">✦ Grounded in real filings · screener.in</span>
            </Reveal>
            <Reveal delay={80}>
              <h1>
                Analyst-style outlook reports,
                <br />
                <span className="grad-text">grounded in real filings</span>
              </h1>
            </Reveal>
            <Reveal delay={160}>
              <p className="hero-sub muted">
                Not another dashboard. ForecastGPT reads the latest results decks and
                earnings calls for any covered NSE company, then writes a
                confidence-scored outlook report for next quarter.
              </p>
            </Reveal>
            <Reveal delay={240}>
              <div className="hero-cta">
                <button className="primary" onClick={onAuth}>
                  Start free →
                </button>
                <button className="ghost" onClick={onSample}>
                  See a live sample
                </button>
              </div>
            </Reveal>
            <Reveal delay={320}>
              <p className="faint small">
                Free daily forecasts · no card · your own key for unlimited runs
              </p>
            </Reveal>
          </div>
          <Reveal delay={200} className="hero-mock-wrap">
            <HeroMock />
          </Reveal>
        </div>
      </section>

      {/* ---------- 2. STATS ---------- */}
      <section className="section">
        <div className="stats-grid">
          <Reveal><StatTile label="companies covered" value={stats?.companies ?? null} /></Reveal>
          <Reveal delay={80}><StatTile label="forecasts run" value={stats?.forecasts_total ?? null} /></Reveal>
          <Reveal delay={160}><StatTile label="completed reports" value={stats?.forecasts_completed ?? null} /></Reveal>
          <Reveal delay={240}><StatTile label="public data source" value={1} /></Reveal>
        </div>
        <p className="faint small center" style={{ marginTop: 8 }}>
          live counters — screener.in filings, processed end-to-end
        </p>
      </section>

      {/* ---------- 3. PROBLEM ---------- */}
      <section className="section" id="problem">
        <Reveal>
          <h2 className="section-title">
            The problem: <span className="grad-text">every quarter, the same archaeology</span>
          </h2>
          <p className="section-sub muted">
            Indian listed companies publish dense investor decks and transcripts —
            and the numbers you need are drawn, not written.
          </p>
        </Reveal>
        <div className="steps">
          {PROBLEMS.map((p, i) => (
            <Reveal key={p.title} delay={i * 90}>
              <div className="glass hover-lift step problem-card">
                <span className="feature-icon">{p.icon}</span>
                <h3>{p.title}</h3>
                <p className="muted">{p.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- 4. SOLUTION ---------- */}
      <section className="section" id="product">
        <div className="solution-grid">
          <Reveal>
            <div>
              <h2 className="section-title" style={{ textAlign: 'left' }}>
                The solution: <span className="grad-text">a grounded report, in minutes</span>
              </h2>
              <div className="solution-points">
                {SOLUTION_POINTS.map((s) => (
                  <div className="solution-point" key={s.title}>
                    <span className="feature-icon">{s.icon}</span>
                    <div>
                      <h3>{s.title}</h3>
                      <p className="muted">{s.body}</p>
                    </div>
                  </div>
                ))}
              </div>
              <button className="primary" onClick={onAuth} style={{ marginTop: 20 }}>
                Generate your first report →
              </button>
            </div>
          </Reveal>
          <Reveal delay={150}>
            <div className="glass card solution-preview">
              <span className="chip mono small">real output · sample run</span>
              <div className="solution-metrics">
                <MetricCard label="Revenue" unit="₹ cr" metricKey="total_revenue_inr_cr" metrics={sampleJob.result?.financial_metrics} />
                <MetricCard label="Margin" unit="%" metricKey="operating_margin_pct" metrics={sampleJob.result?.financial_metrics} decimals={1} />
              </div>
              <blockquote className="forecast-quote">
                {(sampleJob.result?.qualitative_forecast_next_quarter || '').slice(0, 220)}…
              </blockquote>
              <button className="ghost" onClick={onSample}>
                Open the full sample →
              </button>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- 5. HOW IT WORKS ---------- */}
      <section className="section" id="how">
        <Reveal>
          <h2 className="section-title">How it works</h2>
          <p className="section-sub muted">Four steps, fully automated in between.</p>
        </Reveal>
        <div className="steps four">
          {STEPS.map((s, i) => (
            <Reveal key={s.n} delay={i * 80}>
              <div className="glass hover-lift step">
                <span className="step-n grad-text mono">{s.n}</span>
                <h3>{s.title}</h3>
                <p className="muted">{s.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- 6. LIVE SAMPLE ---------- */}
      <section className="section" id="sample">
        <Reveal>
          <h2 className="section-title">
            See a real report, <span className="grad-text">right now</span>
          </h2>
          <p className="section-sub muted">
            This is a genuine completed run over TCS filings — not a mock-up.
          </p>
        </Reveal>
        <Reveal delay={120}>
          <div className="sample-cta glass hover-lift">
            <div className="sample-metrics">
              <MetricCard label="Revenue" unit="₹ cr" metricKey="total_revenue_inr_cr" metrics={sampleJob.result?.financial_metrics} />
              <MetricCard label="Net profit" unit="₹ cr" metricKey="net_profit_inr_cr" metrics={sampleJob.result?.financial_metrics} />
              <MetricCard label="Op. margin" unit="%" metricKey="operating_margin_pct" metrics={sampleJob.result?.financial_metrics} decimals={1} />
            </div>
            <button className="primary" onClick={onSample}>
              Open the full interactive sample →
            </button>
          </div>
        </Reveal>
      </section>

      {/* ---------- 7. FEATURES ---------- */}
      <section className="section" id="features">
        <Reveal>
          <h2 className="section-title">Built like a product, not a demo</h2>
        </Reveal>
        <div className="features">
          {FEATURES.map((f, i) => (
            <Reveal key={f.title} delay={(i % 3) * 80}>
              <div className="glass hover-lift feature">
                <span className="feature-icon">{f.icon}</span>
                <h3>{f.title}</h3>
                <p className="muted">{f.body}</p>
              </div>
            </Reveal>
          ))}
        </div>
      </section>

      {/* ---------- 8. DEVELOPERS ---------- */}
      <section className="section" id="developers">
        <div className="dev-grid">
          <Reveal>
            <div>
              <h2 className="section-title" style={{ textAlign: 'left' }}>
                For developers: <span className="grad-text">the website is just a client</span>
              </h2>
              <p className="muted">
                Mint an API key with the CLI and call the same endpoints the console
                uses. Async by design — submit, poll, get stable JSON. Rate limits
                and per-key quotas are built in.
              </p>
              <a
                className="ghost"
                style={{ display: 'inline-block', marginTop: 16, textDecoration: 'none' }}
                href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent#-api-usage"
                target="_blank"
                rel="noreferrer"
              >
                Full API reference →
              </a>
            </div>
          </Reveal>
          <Reveal delay={140}>
            <div className="dev-code glass">
              <div className="mock-head">
                <span className="mock-dot" />
                <span className="mock-dot" />
                <span className="mock-dot" />
                <span className="mock-title mono">POST /forecasts</span>
              </div>
              <pre className="mono">{DEV_CURL}</pre>
              <pre className="mono resp">{DEV_JSON}</pre>
            </div>
          </Reveal>
        </div>
      </section>

      {/* ---------- 9. FAQ ---------- */}
      <section className="section" id="faq">
        <Reveal>
          <h2 className="section-title">Questions, answered</h2>
        </Reveal>
        <Faq />
      </section>

      {/* ---------- 10. FINAL CTA ---------- */}
      <section className="section">
        <Reveal>
          <div className="cta-strip glass">
            <div>
              <h2>
                Your next quarter, <span className="grad-text">explained</span>.
              </h2>
              <p className="muted">Free daily reports · BYOK for unlimited · API included.</p>
            </div>
            <div className="hero-cta" style={{ margin: 0 }}>
              <button className="primary" onClick={onAuth}>
                Start free →
              </button>
              <button className="ghost" onClick={onLaunch}>
                Open console
              </button>
            </div>
          </div>
        </Reveal>
      </section>
    </div>
  )
}
