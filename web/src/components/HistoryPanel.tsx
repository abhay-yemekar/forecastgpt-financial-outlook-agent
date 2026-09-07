import type { JobSummary } from '../types'
import { timeAgo } from '../format'

interface Props {
  summaries: JobSummary[]
  loading: boolean
  activeJobId: number | null
  onOpen: (jobId: number) => void
  onRefresh: () => void
}

export default function HistoryPanel({ summaries, loading, activeJobId, onOpen, onRefresh }: Props) {
  return (
    <aside className="glass card history fade-up">
      <div className="history-head">
        <h3>Recent forecasts</h3>
        <button className="ghost" onClick={onRefresh} disabled={loading} aria-label="Refresh history">
          ⟳
        </button>
      </div>

      {loading && summaries.length === 0 && (
        <div className="history-list">
          <div className="skeleton" style={{ height: 44, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 44, marginBottom: 8 }} />
          <div className="skeleton" style={{ height: 44 }} />
        </div>
      )}

      {!loading && summaries.length === 0 && (
        <p className="muted small">
          Your completed forecasts will appear here — click one to view it instantly.
        </p>
      )}

      <div className="history-list">
        {summaries.map((s) => {
          const clickable = s.status === 'completed'
          return (
            <button
              key={s.job_id}
              className={`history-row ${clickable ? '' : 'disabled'} ${s.job_id === activeJobId ? 'active' : ''}`}
              onClick={() => clickable && onOpen(s.job_id)}
              disabled={!clickable}
              title={clickable ? 'View this forecast' : s.status === 'failed' ? s.error ?? 'failed' : 'still in progress'}
            >
              <span className={`dot ${s.status}`} />
              <span className="history-co">
                <strong>{s.company ?? '—'}</strong>
                <span className="muted small">#{s.job_id} · {s.status}</span>
              </span>
              <span className="faint small">{timeAgo(s.created_at)}</span>
            </button>
          )
        })}
      </div>
    </aside>
  )
}
