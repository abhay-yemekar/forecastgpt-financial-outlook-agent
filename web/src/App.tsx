import { useCallback, useEffect, useRef, useState } from 'react'
import { fetchCompanies, getForecast, submitForecast } from './api'
import type { Company, Job } from './types'
import SubmitForm from './components/SubmitForm'
import JobStatus from './components/JobStatus'
import ResultView from './components/ResultView'

const KEY_STORAGE = 'fgpt_api_key'
const JOB_STORAGE = 'fgpt_active_job'
const DEFAULT_QUERY =
  'Analyze the latest quarterly results and give a qualitative outlook for the next quarter.'
const POLL_MS = 3000

// A forecast can run for minutes; a page refresh must not lose it.
function loadActiveJob(): { jobId: number; status: string } | null {
  try {
    const raw = localStorage.getItem(JOB_STORAGE)
    if (!raw) return null
    const job = JSON.parse(raw) as { jobId: number; status: string }
    if (!Number.isFinite(job.jobId)) return null
    if (job.status === 'completed' || job.status === 'failed') return null
    return job
  } catch {
    return null
  }
}

function saveActiveJob(job: { jobId: number; status: string } | null) {
  if (job) localStorage.setItem(JOB_STORAGE, JSON.stringify(job))
  else localStorage.removeItem(JOB_STORAGE)
}

export default function App() {
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(KEY_STORAGE) ?? '')
  const [companies, setCompanies] = useState<Company[]>([])
  const [companiesError, setCompaniesError] = useState<string | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const timer = useRef<number | null>(null)

  useEffect(() => {
    fetchCompanies()
      .then(setCompanies)
      .catch((e: Error) => setCompaniesError(e.message))
  }, [])

  useEffect(() => {
    localStorage.setItem(KEY_STORAGE, apiKey)
  }, [apiKey])

  // Resume an in-flight job after a refresh.
  useEffect(() => {
    const active = loadActiveJob()
    if (active && localStorage.getItem(KEY_STORAGE)) {
      setJob({ job_id: active.jobId, status: active.status as Job['status'] })
      poll(active.jobId)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  const poll = useCallback(
    (jobId: number) => {
      stopPolling()
      timer.current = window.setInterval(async () => {
        try {
          const next = await getForecast(apiKey, jobId)
          setJob(next)
          saveActiveJob(
            next.status === 'completed' || next.status === 'failed' ? null : { jobId, status: next.status },
          )
          if (next.status === 'completed' || next.status === 'failed') stopPolling()
        } catch (e) {
          const err = e as Error & { status?: number }
          // A transient 429 must not kill the poller — the next tick will
          // land in a fresh rate-limit window. Anything else is fatal.
          if (err.status === 429) return
          setSubmitError(err.message)
          stopPolling()
          saveActiveJob(null)
        }
      }, POLL_MS)
    },
    [apiKey, stopPolling],
  )

  const onSubmit = useCallback(
    async (company: string, query: string) => {
      setSubmitError(null)
      setSubmitting(true)
      stopPolling()
      setJob(null)
      try {
        const resp = await submitForecast(apiKey, { company, query })
        setJob({ job_id: resp.job_id, status: resp.status })
        saveActiveJob({ jobId: resp.job_id, status: resp.status })
        poll(resp.job_id)
      } catch (e) {
        setSubmitError((e as Error).message)
      } finally {
        setSubmitting(false)
      }
    },
    [apiKey, poll, stopPolling],
  )

  const onReset = useCallback(() => {
    stopPolling()
    setJob(null)
    setSubmitError(null)
    saveActiveJob(null)
  }, [stopPolling])

  const showResult = job?.status === 'completed' && job.result

  return (
    <div className="page">
      <header className="hero">
        <h1>ForecastGPT</h1>
        <p className="subtitle">
          AI-generated quarterly outlook for Indian listed companies — grounded in real filings
          from screener.in.
        </p>
      </header>

      {companiesError && (
        <div className="banner error">Could not reach the API: {companiesError}</div>
      )}

      {!showResult && (
        <SubmitForm
          apiKey={apiKey}
          onApiKeyChange={setApiKey}
          companies={companies}
          defaultQuery={DEFAULT_QUERY}
          submitting={submitting}
          onSubmit={onSubmit}
        />
      )}

      {submitError && <div className="banner error">{submitError}</div>}

      {job && !showResult && (
        <JobStatus job={job} onCancel={onReset} />
      )}

      {showResult && (
        <ResultView job={job!} result={job!.result!} onReset={onReset} />
      )}

      <footer className="footer">
        Same public API developers use: <code>POST /forecasts</code> · <code>GET /forecasts/&#123;id&#125;</code>
      </footer>
    </div>
  )
}
