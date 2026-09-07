import { useState } from 'react'
import type { Company } from '../types'

interface Props {
  apiKey: string
  onApiKeyChange: (key: string) => void
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
  companies,
  defaultQuery,
  submitting,
  onSubmit,
}: Props) {
  const [company, setCompany] = useState('')
  const [query, setQuery] = useState(defaultQuery)
  const [showKey, setShowKey] = useState(false)

  const ready = apiKey.trim() !== '' && company !== '' && query.trim() !== '' && !submitting

  return (
    <section className="glass card form fade-up">
      <label className="field">
        <span>API key</span>
        <div className="key-row">
          <input
            type={showKey ? 'text' : 'password'}
            placeholder="fgpt_…"
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
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
      </label>

      <label className="field">
        <span>Ask</span>
        <textarea rows={3} value={query} onChange={(e) => setQuery(e.target.value)} />
      </label>

      <button className="primary submit-btn" disabled={!ready} onClick={() => onSubmit(company, query)}>
        {submitting ? 'Submitting…' : 'Generate forecast'}
        <span className="submit-hint">~4–6 min · async, keep this tab open</span>
      </button>
    </section>
  )
}
