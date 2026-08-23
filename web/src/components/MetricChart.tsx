import type { FinancialMetrics } from '../types'

const METRICS = [
  { key: 'total_revenue_inr_cr', label: 'Revenue', unit: '₹ cr' },
  { key: 'net_profit_inr_cr', label: 'Net profit', unit: '₹ cr' },
  { key: 'operating_margin_pct', label: 'Operating margin', unit: '%' },
] as const

interface Trend {
  direction?: string
  pct_change?: number
}

function parseNum(v: string | null | undefined): number | null {
  if (v == null) return null
  const n = parseFloat(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}

function DirectionBadge({ trend }: { trend: Trend | undefined }) {
  if (!trend || trend.direction === 'insufficient data') {
    return <span className="badge muted">insufficient data</span>
  }
  const dir = trend.direction ?? '?'
  const cls = dir === 'up' ? 'up' : dir === 'down' ? 'down' : 'flat'
  const arrow = dir === 'up' ? '↑' : dir === 'down' ? '↓' : '→'
  const pct = typeof trend.pct_change === 'number' ? ` ${trend.pct_change > 0 ? '+' : ''}${trend.pct_change}%` : ''
  return (
    <span className={`badge ${cls}`}>
      {arrow}
      {pct}
    </span>
  )
}

function Bars({ values, unit }: { values: number[]; unit: string }) {
  const max = Math.max(...values.map(Math.abs), 1)
  return (
    <div className="bars">
      {values.map((v, i) => (
        <div className="bar-row" key={i}>
          <span className="bar-label">{i === 0 ? 'latest' : 'previous'}</span>
          <div className="bar-track">
            <div
              className={`bar-fill ${i === 0 ? 'latest' : 'prev'}`}
              style={{ width: `${(Math.abs(v) / max) * 100}%` }}
            />
          </div>
          <span className="bar-value">
            {v.toLocaleString('en-IN')} {unit}
          </span>
        </div>
      ))}
    </div>
  )
}

export default function MetricChart({ metrics }: { metrics: FinancialMetrics | undefined }) {
  if (!metrics?.documents?.length) {
    return <p className="muted">No numeric financial metrics were extracted from the filings.</p>
  }

  return (
    <div className="metric-grid">
      {METRICS.map(({ key, label, unit }) => {
        const values: number[] = []
        for (const doc of metrics.documents ?? []) {
          const v = parseNum(doc.metrics?.[key])
          if (v !== null) {
            values.push(v)
            if (values.length === 2) break
          }
        }
        const trend = metrics.trend_summary?.[key] as Trend | undefined
        return (
          <div className="metric" key={key}>
            <div className="metric-head">
              <h4>{label}</h4>
              <DirectionBadge trend={trend} />
            </div>
            {values.length ? (
              <Bars values={values} unit={unit} />
            ) : (
              <p className="muted small">Not found in the filings.</p>
            )}
          </div>
        )
      })}
    </div>
  )
}
