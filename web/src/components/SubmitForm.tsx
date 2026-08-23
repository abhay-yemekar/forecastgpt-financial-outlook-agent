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
    <section className="card form">
      <label className="field">
        <span>API key</span>
        <div className="key-row">
          <input
            type={showKey ? 'text' : 'password'}
            placeholder="fgpt_..."
            value={apiKey}
            onChange={(e) => onApiKeyChange(e.target.value)}
            spellCheck={false}
          />
          <button type="button" className="ghost" onClick={() => setShowKey((s) => !s)}>
            {showKey ? 'Hide' : 'Show'}
          </button>
        </div>
        <small>Issued via <code>python -m app.cli key create</code>. Stored only in your browser.</small>
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
        <span>Query</span>
        <textarea rows={3} value={query} onChange={(e) => setQuery(e.target.value)} />
      </label>

      <button className="primary" disabled={!ready} onClick={() => onSubmit(company, query)}>
        {submitting ? 'Submitting…' : 'Generate forecast'}
      </button>
    </section>
  )
}
