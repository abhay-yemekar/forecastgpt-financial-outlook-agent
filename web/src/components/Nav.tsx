import type { QuotaInfo } from '../api'

interface Props {
  view: 'landing' | 'app'
  onNav: (view: 'landing' | 'app') => void
  hasAuth: boolean
  quota: QuotaInfo | null
}

export default function Nav({ view, onNav, hasAuth, quota }: Props) {
  return (
    <nav className="nav glass">
      <button className="nav-brand" onClick={() => onNav('landing')} aria-label="ForecastGPT home">
        <img src="/favicon.svg" alt="" width="26" height="26" />
        <span>
          Forecast<span className="grad-text">GPT</span>
        </span>
      </button>

      <div className="nav-right">
        <button className="ghost" onClick={() => onNav(view === 'landing' ? 'app' : 'landing')}>
          {view === 'landing' ? 'Console' : 'Overview'}
        </button>
        <a
          className="nav-link"
          href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent"
          target="_blank"
          rel="noreferrer"
        >
          GitHub
        </a>
        {quota?.quota === 'free_tier' && typeof quota.used === 'number' && typeof quota.limit === 'number' && (
          <span
            className={`chip key-chip ${quota.used >= quota.limit ? 'quota-out' : ''}`}
            title={`Free daily quota: ${quota.used}/${quota.limit} used · resets ${quota.resets_at}`}
          >
            <span className={`dot ${quota.used >= quota.limit ? 'failed' : 'completed'}`} />
            {quota.limit - quota.used} left today
          </span>
        )}
        <span className={`chip key-chip ${hasAuth ? 'ok' : ''}`} title={hasAuth ? 'Signed in' : 'No API key — sample available'}>
          <span className={`dot ${hasAuth ? 'completed' : 'queued'}`} />
          {hasAuth ? 'Connected' : 'No key'}
        </span>
      </div>
    </nav>
  )
}
