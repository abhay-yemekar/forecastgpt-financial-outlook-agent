import type { Job } from '../types'

export default function JobStatus({ job, onCancel }: { job: Job; onCancel: () => void }) {
  const detail =
    job.status === 'queued'
      ? 'Waiting for a worker to pick it up…'
      : job.status === 'running'
        ? 'Fetching filings, extracting metrics, running RAG + LLM… this usually takes a few minutes.'
        : job.error ?? 'Something went wrong.'

  return (
    <section className={`card status ${job.status === 'failed' ? 'error' : ''}`}>
      <div className="status-head">
        <span className={`dot ${job.status}`} />
        <h2>
          Job #{job.job_id} — {job.status}
          {job.company ? ` · ${job.company}` : ''}
        </h2>
      </div>
      <p className="muted">{detail}</p>
      {job.status === 'failed' && <button className="ghost" onClick={onCancel}>Try again</button>}
      {job.status !== 'failed' && (
        <p className="muted small">This page polls <code>GET /forecasts/{job.job_id}</code> every few seconds.</p>
      )}
    </section>
  )
}
