import type { ForecastResult, Job } from '../types'
import MetricChart from './MetricChart'

function List({ title, items, tone }: { title: string; items?: string[]; tone: string }) {
  if (!items?.length) return null
  return (
    <div className={`card list ${tone}`}>
      <h3>{title}</h3>
      <ul>
        {items.map((it, i) => (
          <li key={i}>{it}</li>
        ))}
      </ul>
    </div>
  )
}

export default function ResultView({
  job,
  result,
  onReset,
}: {
  job: Job
  result: ForecastResult
  onReset: () => void
}) {
  const confidence = result.confidence?.level ?? 'unknown'
  const price = result.market_context?.price_inr
  const trends = result.financial_trends ?? {}

  return (
    <div className="results">
      <section className="card result-head">
        <div>
          <h2>{result.company ?? job.company ?? 'Forecast'}</h2>
          {result.period_analyzed?.length ? (
            <p className="muted">Periods analyzed: {result.period_analyzed.join(' · ')}</p>
          ) : null}
        </div>
        <div className="head-badges">
          {price != null && (
            <span className="badge flat">
              {result.market_context?.symbol}: ₹{price.toLocaleString('en-IN')}
            </span>
          )}
          <span className={`badge conf-${confidence}`}>confidence: {confidence}</span>
        </div>
      </section>

      <section className="card">
        <h3>Extracted financials — quarter over quarter</h3>
        <MetricChart metrics={result.financial_metrics} />
      </section>

      <div className="trend-cards">
        {(
          [
            ['Revenue', trends.revenue],
            ['Net profit', trends.net_profit],
            ['Operating margin', trends.operating_margin],
          ] as const
        ).map(([label, text]) =>
          text ? (
            <div className="card trend" key={label}>
              <h4>{label}</h4>
              <p>{text}</p>
            </div>
          ) : null,
        )}
      </div>

      <section className="card forecast">
        <h3>Outlook for next quarter</h3>
        <p>{result.qualitative_forecast_next_quarter || '—'}</p>
        {result.confidence?.reasons?.length ? (
          <p className="muted small">Basis: {result.confidence.reasons.join(' · ')}</p>
        ) : null}
      </section>

      <div className="list-grid">
        <List title="Management themes" items={result.management_themes} tone="neutral" />
        <List title="Risks" items={result.risks} tone="risk" />
        <List title="Opportunities" items={result.opportunities} tone="opp" />
      </div>

      <div className="actions">
        <button className="primary" onClick={onReset}>
          New forecast
        </button>
        <span className="muted small">
          Job #{job.job_id} · completed {job.created_at ? new Date(job.created_at).toLocaleString() : ''}
        </span>
      </div>
    </div>
  )
}
