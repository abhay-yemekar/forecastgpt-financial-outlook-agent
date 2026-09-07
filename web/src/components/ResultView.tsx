import { useState } from 'react'
import type { ForecastResult, Job } from '../types'
import ConfidenceGauge from './ConfidenceGauge'
import MetricCard from './MetricCard'

function ChipList({ items }: { items?: string[] }) {
  if (!items?.length) return null
  return (
    <ul className="chiplist">
      {items.map((it, i) => (
        <li className="chip" key={i}>
          {it}
        </li>
      ))}
    </ul>
  )
}

export default function ResultView({
  job,
  result,
  sample = false,
  onReset,
}: {
  job: Job
  result: ForecastResult
  sample?: boolean
  onReset: () => void
}) {
  const [copied, setCopied] = useState(false)
  const price = result.market_context?.price_inr
  const trends = result.financial_trends ?? {}
  const fm = result.financial_metrics

  const copyJson = async () => {
    try {
      await navigator.clipboard.writeText(JSON.stringify(result, null, 2))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1600)
    } catch {
      /* clipboard unavailable */
    }
  }

  return (
    <div className="results">
      {sample && (
        <div className="banner info">
          ✦ Sample result — a real completed TCS run. <strong>Launch your own forecast for live data.</strong>
        </div>
      )}

      <section className="glass card result-head fade-up">
        <div className="result-id">
          <h2>{result.company ?? job.company ?? 'Forecast'}</h2>
          <div className="head-chips">
            {job.company && <span className="chip mono">{job.company}</span>}
            {price != null && (
              <span className="chip">
                <span className="muted small">last</span>
                <strong className="mono">₹{price.toLocaleString('en-IN')}</strong>
              </span>
            )}
            {result.period_analyzed?.length ? (
              <span className="chip">{result.period_analyzed.join(' · ')}</span>
            ) : null}
          </div>
        </div>
        <ConfidenceGauge level={result.confidence?.level} />
      </section>

      <section className="fade-up d1">
        <h3 className="results-section-title">Quarter-over-quarter metrics</h3>
        <div className="metric-grid">
          <svg width="0" height="0" aria-hidden="true">
            <defs>
              <linearGradient id="bar-grad" x1="0" y1="1" x2="0" y2="0">
                <stop offset="0%" stopColor="#8b5cf6" />
                <stop offset="100%" stopColor="#22d3ee" />
              </linearGradient>
            </defs>
          </svg>
          <MetricCard label="Revenue" unit="₹ cr" metricKey="total_revenue_inr_cr" metrics={fm} />
          <MetricCard label="Net profit" unit="₹ cr" metricKey="net_profit_inr_cr" metrics={fm} />
          <MetricCard
            label="Operating margin"
            unit="%"
            metricKey="operating_margin_pct"
            metrics={fm}
            decimals={1}
          />
        </div>
      </section>

      {([['Revenue', trends.revenue], ['Net profit', trends.net_profit], ['Operating margin', trends.operating_margin]] as const).some(
        ([, v]) => v,
      ) && (
        <section className="trend-cards fade-up d2">
          {([['Revenue', trends.revenue], ['Net profit', trends.net_profit], ['Operating margin', trends.operating_margin]] as const).map(
            ([label, text]) =>
              text ? (
                <div className="glass hover-lift trend" key={label}>
                  <h4>{label}</h4>
                  <p className="muted">{text}</p>
                </div>
              ) : null,
          )}
        </section>
      )}

      <section className="glass card forecast-block fade-up d3">
        <h3>Outlook for next quarter</h3>
        <blockquote className="forecast-quote">{result.qualitative_forecast_next_quarter || '—'}</blockquote>
        {result.confidence?.reasons?.length ? (
          <p className="faint small">Basis: {result.confidence.reasons.join(' · ')}</p>
        ) : null}
      </section>

      <div className="list-grid fade-up d4">
        {result.management_themes?.length ? (
          <div className="glass card list neutral">
            <h3>Management themes</h3>
            <ChipList items={result.management_themes} />
          </div>
        ) : null}
        {result.risks?.length ? (
          <div className="glass card list risk">
            <h3>Risks</h3>
            <ChipList items={result.risks} />
          </div>
        ) : null}
        {result.opportunities?.length ? (
          <div className="glass card list opp">
            <h3>Opportunities</h3>
            <ChipList items={result.opportunities} />
          </div>
        ) : null}
      </div>

      <div className="actions fade-up d5">
        <button className="primary" onClick={onReset}>
          {sample ? 'Run a real forecast' : 'New forecast'}
        </button>
        <button className="ghost" onClick={copyJson}>
          {copied ? '✓ Copied' : 'Copy JSON'}
        </button>
        <details className="raw-json">
          <summary className="muted small">View raw JSON</summary>
          <pre className="mono">{JSON.stringify(result, null, 2)}</pre>
        </details>
      </div>

      {!sample && (
        <p className="faint small">
          Job #{job.job_id} · completed {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
        </p>
      )}
    </div>
  )
}
