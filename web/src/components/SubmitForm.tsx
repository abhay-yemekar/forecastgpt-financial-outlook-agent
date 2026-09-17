import { useState } from 'react'
import type { Company } from '../types'
import { PROMPT_GROUPS } from '../content/prompts'

interface Props {
  apiKey: string
  onApiKeyChange?: (key: string) => void
  hideKeyField?: boolean
  providerKey?: string
  onProviderKeyChange?: (key: string) => void
  companies: Company[]
  defaultQuery: string
  submitting: boolean
  onSubmit: (company: string, query: string) => void
}

const KEY_CLI = 'python -m app.cli key create --email you@example.com --password your-password'

function CopyButton({ text }: { text: string }) {
  const [copied, setCopied] = useState(false)
  return (
    <button
      className="ghost"
      onClick={async () => {
        try {
          await navigator.clipboard.writeText(text)
          setCopied(true)
          window.setTimeout(() => setCopied(false), 1500)
        } catch {
          /* clipboard unavailable */
        }
      }}
    >
      {copied ? '✓ copied' : 'Copy'}
    </button>
  )
}

export default function SubmitForm({
  apiKey,
  onApiKeyChange,
  hideKeyField = false,
  providerKey,
  onProviderKeyChange,
  companies,
  defaultQuery,
  submitting,
  onSubmit,
}: Props) {
  const [company, setCompany] = useState('')
  const [query, setQuery] = useState(defaultQuery)
  const [showKey, setShowKey] = useState(false)

  const ready =
    (hideKeyField || apiKey.trim() !== '') &&
    (hideKeyField || query.trim() !== '') &&
    company !== '' &&
    query.trim() !== '' &&
    !submitting

  const changeApiKey = (key: string) => onApiKeyChange?.(key)

  return (
    <section className="glass card form fade-up">
      {!hideKeyField && (
        <label className="field">
          <span>API key (developer mode)</span>
          <div className="key-row">
            <input
              type={showKey ? 'text' : 'password'}
              placeholder="fgpt_…"
              value={apiKey}
              onChange={(e) => changeApiKey(e.target.value)}
              spellCheck={false}
              className="mono"
            />
            <button type="button" className="ghost" onClick={() => setShowKey((s) => !s)}>
              {showKey ? 'Hide' : 'Show'}
            </button>
          </div>
          <details className="key-help">
            <summary className="muted small">How do I get a key?</summary>
            <p className="muted small">
              Run this against your ForecastGPT instance, then paste the printed <code>fgpt_…</code> key:
            </p>
            <div className="code-row">
              <code>{KEY_CLI}</code>
              <CopyButton text={KEY_CLI} />
            </div>
          </details>
        </label>
      )}

      {hideKeyField && onProviderKeyChange && (
        <label className="field">
          <span>Your own provider key (optional — bypasses the free quota)</span>
          <input
            type="password"
            placeholder="Paste a key for the server's LLM provider…"
            value={providerKey ?? ''}
            onChange={(e) => onProviderKeyChange(e.target.value)}
            spellCheck={false}
            className="mono"
          />
          <small className="muted">
            Used for this browser's requests only — never stored server-side.
          </small>
        </label>
      )}

      <label className="field">
        <span>Company</span>
        <select value={company} onChange={(e) => setCompany(e.target.value)}>
          <option value="" disabled>
            {companies.length ? 'Select a company…' : 'Loading companies…'}
          </option>
          {companies.map((c) => (
            <option key={c.symbol} value={c.symbol}>
              {c.display_name} ({c.symbol})
            </option>
          ))}
        </select>
        <details className="key-help">
          <summary className="muted small">Company not listed?</summary>
          <p className="muted small">
            The registry grows release by release. Request an addition via{' '}
            <a href="mailto:yemekarabhays@gmail.com?subject=ForecastGPT%20company%20request">email</a>{' '}
            or a{' '}
            <a
              href="https://github.com/abhay-yemekar/forecastgpt-financial-outlook-agent/issues/new?title=Company%20request%3A%20"
              target="_blank"
              rel="noreferrer"
            >
              GitHub issue
            </a>{' '}
            — include the NSE symbol. Self-hosters can add it in one line
            (`SEED_COMPANIES` in <code>app/companies.py</code>).
          </p>
        </details>
      </label>

      <div className="field">
        <span>Ask — pick a starting point or write your own</span>
        <div className="prompt-groups">
          {PROMPT_GROUPS.map((g) => (
            <details className="prompt-group" key={g.category}>
              <summary>
                <span className="pg-icon">{g.icon}</span>
                {g.category}
                <span className="pg-count">{g.prompts.length}</span>
              </summary>
              <div className="pg-list">
                {g.prompts.map((p) => (
                  <button
                    key={p}
                    type="button"
                    className={`pg-prompt ${query === p ? 'active' : ''}`}
                    onClick={() => setQuery(p)}
                    title="Use this prompt"
                  >
                    {p}
                  </button>
                ))}
              </div>
            </details>
          ))}
        </div>
        <textarea
          rows={3}
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="What do you want to know about next quarter?"
          style={{ marginTop: 10 }}
        />
      </div>

      <button className="primary submit-btn" disabled={!ready} onClick={() => onSubmit(company, query)}>
        {submitting ? 'Submitting…' : 'Generate forecast'}
        <span className="submit-hint">~4–6 min · async, keep this tab open</span>
      </button>
    </section>
  )
}
