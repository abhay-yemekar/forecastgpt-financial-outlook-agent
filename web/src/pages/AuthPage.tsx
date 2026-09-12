import { useEffect } from 'react'
import AuthPanel, { type SessionInfo } from '../components/AuthPanel'
import HeroMock from '../components/HeroMock'

interface Props {
  session: SessionInfo | null
  onSession: (s: SessionInfo | null) => void
  onReady: () => void // called when the user is signed in (parent routes to console)
}

const POINTS = [
  { icon: '◈', text: 'Grounded in real filings — every number traceable to a page' },
  { icon: '❖', text: 'Earnings-call RAG, not generic model guesses' },
  { icon: '⧗', text: 'A few free forecasts daily — bring your own key for unlimited' },
]

export default function AuthPage({ session, onSession, onReady }: Props) {
  // Already signed in? Straight to the console.
  useEffect(() => {
    if (session) onReady()
  }, [session, onReady])

  return (
    <div className="auth-page">
      <section className="auth-brand">
        <div className="orb orb-a" />
        <div className="orb orb-b" />
        <span className="chip hero-eyebrow">✦ ForecastGPT</span>
        <h2>
          Your next-quarter <span className="grad-text">outlook report</span> is minutes away.
        </h2>
        <ul className="auth-points">
          {POINTS.map((p, i) => (
            <li key={p.icon} className={`fade-up d${i + 1}`}>
              <span className="feature-icon">{p.icon}</span>
              {p.text}
            </li>
          ))}
        </ul>
        <div className="auth-brand-mock">
          <HeroMock />
        </div>
      </section>

      <section className="auth-form-side">
        <div className="glass card auth-card fade-up">
          <h2>Welcome back</h2>
          <p className="muted small" style={{ marginBottom: 16 }}>
            Sign in to run forecasts, track your history, and manage your reports.
          </p>
          <AuthPanel session={session} onSession={onSession} />
        </div>
        <p className="muted small center">
          Prefer a key? Developers can skip login entirely —{' '}
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent#-api-usage" target="_blank" rel="noreferrer">
            use the API directly
          </a>
          .
        </p>
      </section>
    </div>
  )
}
