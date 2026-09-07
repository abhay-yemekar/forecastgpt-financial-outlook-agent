import { useEffect, useState } from 'react'
import type { Job } from '../types'
import { fmtElapsed } from '../format'

const ACTIVITIES = [
  'fetching latest filings from screener.in…',
  'downloading results decks & transcripts…',
  'extracting revenue, profit and margin…',
  'embedding transcripts into the FAISS index…',
  'reasoning over metrics + management commentary…',
  'composing the structured outlook…',
]

interface Props {
  job: Job
  startedAt: number
  onCancel: () => void
}

export default function JobTimeline({ job, startedAt, onCancel }: Props) {
  const [now, setNow] = useState(Date.now())
  const [activityIdx, setActivityIdx] = useState(0)

  const running = job.status === 'running' || job.status === 'queued'

  useEffect(() => {
    if (!running) return
    const t = window.setInterval(() => setNow(Date.now()), 1000)
    return () => window.clearInterval(t)
  }, [running])

  useEffect(() => {
    if (!running) return
    const t = window.setInterval(
      () => setActivityIdx((i) => (i + 1) % ACTIVITIES.length),
      4200,
    )
    return () => window.clearInterval(t)
  }, [running])

  const steps: { key: string; label: string; state: 'done' | 'active' | 'todo' | 'bad' }[] = [
    {
      key: 'submitted',
      label: 'Job accepted',
      state: 'done',
    },
    {
      key: 'queue',
      label: 'Queued',
      state:
        job.status === 'queued'
          ? 'active'
          : job.status === 'failed'
            ? 'done'
            : 'done',
    },
    {
      key: 'run',
      label: 'Running the agent',
      state: job.status === 'running' ? 'active' : job.status === 'completed' ? 'done' : job.status === 'failed' ? 'bad' : 'todo',
    },
    {
      key: 'done',
      label: job.status === 'failed' ? 'Failed' : 'Outlook ready',
      state: job.status === 'completed' ? 'done' : job.status === 'failed' ? 'bad' : 'todo',
    },
  ]

  return (
    <section className={`glass card timeline fade-up ${job.status === 'failed' ? 'error' : ''}`}>
      <div className="timeline-head">
        <h2>
          <span className={`dot ${job.status}`} />
          Forecast #{job.job_id}
          {job.company ? <span className="muted"> · {job.company}</span> : null}
        </h2>
        {running && <span className="mono elapsed">{fmtElapsed(startedAt, now)}</span>}
      </div>

      <ol className="stepper">
        {steps.map((s) => (
          <li key={s.key} className={`step-${s.state}`}>
            <span className="step-marker" />
            <span>{s.label}</span>
          </li>
        ))}
      </ol>

      {running && (
        <>
          <div className="shimmer-bar" />
          <p className="muted small activity">
            <span className="activity-label">current activity</span>
            <span key={activityIdx} className="fade-up activity-text">
              {ACTIVITIES[activityIdx]}
            </span>
          </p>
        </>
      )}

      {job.status === 'failed' && (
        <>
          <p className="banner error">{job.error || 'The forecast job failed.'}</p>
          <button className="ghost" onClick={onCancel}>
            Try again
          </button>
        </>
      )}
    </section>
  )
}
