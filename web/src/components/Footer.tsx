import { CONTACT } from '../content/site'

interface Props {
  onNav: (v: 'landing' | 'app' | 'auth' | 'developers' | 'privacy' | 'terms') => void
}

export default function Footer({ onNav }: Props) {
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
          <div className="contact-links">
            <a className="chip" href={`mailto:${CONTACT.email}`}>
              ✉ {CONTACT.email}
            </a>
            <a className="chip" href={CONTACT.linkedin} target="_blank" rel="noreferrer">
              in LinkedIn
            </a>
            <a className="chip" href={CONTACT.github} target="_blank" rel="noreferrer">
              ⌥ GitHub
            </a>
          </div>
        </div>

        <div className="footer-col">
          <h4>Product</h4>
          <button onClick={() => onNav('landing')}>Overview</button>
          <button onClick={() => onNav('app')}>Console</button>
          <button onClick={() => onNav('auth')}>Sign in</button>
        </div>

        <div className="footer-col">
          <h4>Developers</h4>
          <button onClick={() => onNav('developers')}>API reference</button>
          <a href={CONTACT.repo} target="_blank" rel="noreferrer">
            GitHub repository
          </a>
          <a href={CONTACT.deployGuide} target="_blank" rel="noreferrer">
            Self-host guide
          </a>
        </div>

        <div className="footer-col">
          <h4>Data sources</h4>
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
        <span className="faint small">© {year} ForecastGPT · {CONTACT.name} · MIT License</span>
        <span className="footer-legal faint small">
          <button onClick={() => onNav('privacy')}>Privacy Policy</button>
          <span>·</span>
          <button onClick={() => onNav('terms')}>Terms of Use</button>
          <span>·</span>
          <span>Not investment advice — AI-generated from public filings.</span>
        </span>
      </div>
    </footer>
  )
}
