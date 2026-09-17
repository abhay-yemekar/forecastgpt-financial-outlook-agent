import type { QuotaInfo } from '../api'

interface Props {
  view: 'landing' | 'auth' | 'app' | 'developers' | 'privacy' | 'terms'
  onNav: (v: 'landing' | 'app' | 'auth' | 'developers' | 'privacy' | 'terms') => void
  quota: QuotaInfo | null
  signedInEmail: string | null
  onSignOut: () => void
}

const SECTIONS = [
  { id: 'problem', label: 'Why' },
  { id: 'how', label: 'How it works' },
  { id: 'sample', label: 'Sample' },
  { id: 'faq', label: 'FAQ' },
  { id: 'contact', label: 'Contact' },
]

export default function Nav({ view, onNav, quota, signedInEmail, onSignOut }: Props) {
  const scrollTo = (id: string) => {
    if (view !== 'landing') {
      onNav('landing')
      window.setTimeout(() => document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' }), 120)
    } else {
      document.getElementById(id)?.scrollIntoView({ behavior: 'smooth' })
    }
  }

  return (
    <nav className="nav glass">
      <button className="nav-brand" onClick={() => onNav('landing')} aria-label="ForecastGPT home">
        <img src="/favicon.svg" alt="" width="26" height="26" />
        <span>
          Forecast<span className="grad-text">GPT</span>
        </span>
      </button>

      {view === 'landing' && (
        <div className="nav-links">
          {SECTIONS.map((s) => (
            <button key={s.id} className="nav-link-btn" onClick={() => scrollTo(s.id)}>
              {s.label}
            </button>
          ))}
        </div>
      )}

      <div className="nav-right">
        {quota?.quota === 'free_tier' && typeof quota.used === 'number' && typeof quota.limit === 'number' && (
          <span
            className={`chip key-chip ${quota.used >= quota.limit ? 'quota-out' : ''}`}
            title={`Free daily quota: ${quota.used}/${quota.limit} used · resets ${quota.resets_at}`}
          >
            <span className={`dot ${quota.used >= quota.limit ? 'failed' : 'completed'}`} />
            {quota.limit - quota.used} left today
          </span>
        )}

        <button className="nav-link-btn" onClick={() => onNav('developers')}>
          API
        </button>
        {signedInEmail ? (
          <>
            <span className="chip" title={signedInEmail}>
              <span className="dot completed" />
              {signedInEmail.split('@')[0]}
            </span>
            <button className="ghost" onClick={onSignOut}>
              Sign out
            </button>
            <button className="primary nav-cta" onClick={() => onNav('app')}>
              Console
            </button>
          </>
        ) : (
          <>
            <button className="ghost" onClick={() => onNav('auth')}>
              Sign in
            </button>
            <button className="primary nav-cta" onClick={() => onNav('auth')}>
              Get started
            </button>
          </>
        )}
      </div>
    </nav>
  )
}
