export default function Footer({ onNav }: { onNav: (v: 'landing' | 'app') => void }) {
  const year = new Date().getFullYear()
  return (
    <footer className="site-footer">
      <div className="site-footer-main">
        <div className="footer-brand">
          <span className="footer-logo">
            <img src="/favicon.svg" alt="" width="24" height="24" />
            Forecast<span className="grad-text">GPT</span>
          </span>
          <p className="muted small">
            Quarterly outlook reports for Indian listed companies — grounded in
            real filings, delivered as an API and a console.
          </p>
          <span className="chip mono small">MIT License</span>
        </div>

        <div className="footer-col">
          <h4>Product</h4>
          <button onClick={() => onNav('landing')}>Overview</button>
          <button onClick={() => onNav('app')}>Console</button>
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent#readme" target="_blank" rel="noreferrer">
            How it works
          </a>
        </div>

        <div className="footer-col">
          <h4>Developers</h4>
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent" target="_blank" rel="noreferrer">
            GitHub repository
          </a>
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent#-api-usage" target="_blank" rel="noreferrer">
            API reference
          </a>
          <a href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent/blob/main/docs/DEPLOY.md" target="_blank" rel="noreferrer">
            Self-host guide
          </a>
        </div>

        <div className="footer-col">
          <h4>Data</h4>
          <a href="https://www.screener.in" target="_blank" rel="noreferrer">
            screener.in
          </a>
          <a href="https://www.nseindia.com" target="_blank" rel="noreferrer">
            NSE India
          </a>
          <a href="https://www.bseindia.com" target="_blank" rel="noreferrer">
            BSE India
          </a>
        </div>
      </div>

      <div className="footer-bar">
        <span className="faint small">© {year} ForecastGPT · open source, MIT</span>
        <span className="faint small">
          Not investment advice. Reports are AI-generated from public filings.
        </span>
      </div>
    </footer>
  )
}
