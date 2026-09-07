import { Bar, BarChart, Cell, ResponsiveContainer, Tooltip, XAxis } from 'recharts'
import type { FinancialMetrics } from '../types'
import { fmtINR, parseMetricNum } from '../format'
import { useCountUp } from '../useCountUp'

interface Props {
  label: string
  unit: string
  metricKey: string
  metrics: FinancialMetrics | undefined
  decimals?: number
}

interface Trend {
  direction?: string
  pct_change?: number
}

function DirectionBadge({ trend }: { trend: Trend | undefined }) {
  if (!trend || trend.direction === 'insufficient data' || !trend.direction) {
    return <span className="badge muted">no comparison</span>
  }
  const dir = trend.direction
  const cls = dir === 'up' ? 'up' : dir === 'down' ? 'down' : 'flat'
  const arrow = dir === 'up' ? '↑' : dir === 'down' ? '↓' : '→'
  const pct =
    typeof trend.pct_change === 'number'
      ? ` ${trend.pct_change > 0 ? '+' : ''}${trend.pct_change}%`
      : ''
  return (
    <span className={`badge ${cls}`}>
      {arrow}
      {pct}
    </span>
  )
}

function MiniTooltip({ active, payload, unit }: any) {
  if (!active || !payload?.length) return null
  const p = payload[0].payload as { bucket: string; value: number }
  return (
    <div className="chart-tip">
      {p.bucket}: {fmtINR(p.value)} {unit}
    </div>
  )
}

export default function MetricCard({ label, unit, metricKey, metrics, decimals = 0 }: Props) {
  const values: number[] = []
  for (const doc of metrics?.documents ?? []) {
    const v = parseMetricNum(doc.metrics?.[metricKey])
    if (v !== null) {
      values.push(v)
      if (values.length === 2) break
    }
  }
  const trend = metrics?.trend_summary?.[metricKey] as Trend | undefined
  const latest = values[0] ?? null
  const animated = useCountUp(latest)

  const data =
    values.length > 0
      ? [
          { bucket: 'latest', value: values[0] },
          ...(values[1] !== undefined ? [{ bucket: 'previous', value: values[1] }] : []),
        ]
      : []

  return (
    <div className="glass hover-lift metric-card fade-up">
      <div className="metric-head">
        <h4>{label}</h4>
        <DirectionBadge trend={trend} />
      </div>

      {latest !== null ? (
        <>
          <div className="metric-value mono">
            {animated.toLocaleString('en-IN', {
              minimumFractionDigits: decimals,
              maximumFractionDigits: decimals,
            })}
            <span className="metric-unit"> {unit}</span>
          </div>
          <div className="metric-chart">
            <ResponsiveContainer width="100%" height={64}>
              <BarChart data={data} margin={{ top: 4, right: 0, bottom: 0, left: 0 }} barCategoryGap="28%">
                <XAxis dataKey="bucket" tick={{ fill: '#6b7490', fontSize: 10 }} axisLine={false} tickLine={false} />
                <Tooltip content={<MiniTooltip unit={unit} />} cursor={{ fill: 'rgba(255,255,255,0.04)' }} />
                <Bar dataKey="value" radius={[5, 5, 0, 0]} animationDuration={800}>
                  {data.map((_, i) => (
                    <Cell key={i} fill={i === 0 ? 'url(#bar-grad)' : 'rgba(255,255,255,0.13)'} />
                  ))}
                </Bar>
              </BarChart>
            </ResponsiveContainer>
          </div>
        </>
      ) : (
        <p className="muted small" style={{ padding: '18px 0 10px' }}>
          Not found in the retrieved filings.
        </p>
      )}
    </div>
  )
}
