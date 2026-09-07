import type { Stats } from '../types'

interface Props {
  stats: Stats | null
  onSample: () => void
  onLaunch: () => void
}

const STEPS = [
  {
    n: '01',
    title: 'Pick a company',
    body: 'Any covered NSE-listed company — TCS, Infosys, HDFC Bank and more, from a seeded registry.',
  },
  {
    n: '02',
    title: 'The agent reads real filings',
    body: 'It discovers the latest results decks and earnings-call transcripts from screener.in, extracts the numbers, and runs RAG over management commentary.',
  },
  {
    n: '03',
    title: 'Get a structured outlook',
    body: 'A grounded, confidence-scored JSON forecast for the next quarter — revenue, profit, margin direction, risks, and opportunities.',
  },
]

const FEATURES = [
  {
    icon: '◈',
    title: 'Grounded, not guessed',
    body: 'Every forecast cites the documents it was built from. Missing metrics stay missing — no hallucinated numbers.',
  },
  {
    icon: '❖',
    title: 'Earnings-call RAG',
    body: 'FAISS retrieval over transcripts surfaces management themes, guidance, and risks in their own words.',
  },
  {
    icon: '⧗',
    title: 'Async by design',
    body: 'Forecasts take minutes, not milliseconds. Jobs queue on Redis; you poll. The HTTP request returns in milliseconds.',
  },
  {
    icon: '⌘',
    title: 'API-first',
    body: 'This console uses the exact public API: X-API-Key auth, rate limits, and a stable JSON contract.',
  },
]

export default function Landing({ stats, onSample, onLaunch }: Props) {
  return (
    <div className="landing">
      <section className="hero">
        <div className="orb orb-a" />
        <div className="orb orb-b" />

        <div className="fade-up">
          <span className="chip hero-eyebrow">✦ Grounded in real filings · screener.in</span>
        </div>
        <h1 className="fade-up d1">
          The quarterly outlook engine
          <br />
          for <span className="grad-text">Indian listed companies</span>
        </h1>
        <p className="hero-sub muted fade-up d2">
          ForecastGPT reads the latest results decks and earnings calls, then produces a
          confidence-scored outlook for the next quarter — as an API and a console.
        </p>

        <div className="hero-cta fade-up d3">
          <button className="primary" onClick={onSample}>
            See a live sample →
          </button>
          <button className="ghost" onClick={onLaunch}>
            Launch the console
          </button>
        </div>

        <div className="hero-stats fade-up d4">
          <div className="chip">
            <strong className="mono">{stats ? stats.companies : '—'}</strong> companies covered
          </div>
          <div className="chip">
            <strong className="mono">{stats ? stats.forecasts_total : '—'}</strong> forecasts run
          </div>
          <div className="chip">
            <strong className="mono">{stats ? stats.forecasts_completed : '—'}</strong> completed
          </div>
        </div>
      </section>

      <section className="section">
        <h2 className="section-title fade-up">How it works</h2>
        <div className="steps">
          {STEPS.map((s, i) => (
            <div className={`glass hover-lift step fade-up d${i + 1}`} key={s.n}>
              <span className="step-n grad-text mono">{s.n}</span>
              <h3>{s.title}</h3>
              <p className="muted">{s.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section">
        <h2 className="section-title fade-up">Built like a product, not a demo</h2>
        <div className="features">
          {FEATURES.map((f, i) => (
            <div className={`glass hover-lift feature fade-up d${i + 1}`} key={f.title}>
              <span className="feature-icon">{f.icon}</span>
              <h3>{f.title}</h3>
              <p className="muted">{f.body}</p>
            </div>
          ))}
        </div>
      </section>

      <section className="section cta-strip glass fade-up">
        <div>
          <h2>See a real forecast, instantly</h2>
          <p className="muted">
            The sample is a genuine completed run over TCS filings — no signup, no waiting.
          </p>
        </div>
        <button className="primary" onClick={onSample}>
          View sample forecast
        </button>
      </section>
    </div>
  )
}
