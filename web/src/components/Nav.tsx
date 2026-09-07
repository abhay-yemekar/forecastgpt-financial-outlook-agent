interface Props {
  view: 'landing' | 'app'
  onNav: (view: 'landing' | 'app') => void
  hasKey: boolean
}

export default function Nav({ view, onNav, hasKey }: Props) {
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
        <span className={`chip key-chip ${hasKey ? 'ok' : ''}`} title={hasKey ? 'API key connected' : 'No API key — sample available'}>
          <span className={`dot ${hasKey ? 'completed' : 'queued'}`} />
          {hasKey ? 'Key connected' : 'No key'}
        </span>
      </div>
    </nav>
  )
}
