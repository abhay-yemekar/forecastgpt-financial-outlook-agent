import { useCallback, useEffect, useRef, useState } from 'react'
import {
  fetchCompanies,
  fetchQuotaMe,
  fetchStats,
  getForecast,
  listForecasts,
  submitForecast,
  type Auth,
  type QuotaInfo,
} from './api'
import { supabase } from './lib/supabase'
import sampleJob from './data/sampleResult.json'
import type { Company, Job, JobSummary, Stats } from './types'
import Landing from './components/Landing'
import Nav from './components/Nav'
import SubmitForm from './components/SubmitForm'
import JobTimeline from './components/JobTimeline'
import ResultView from './components/ResultView'
import HistoryPanel from './components/HistoryPanel'
import Footer from './components/Footer'
import AuthPage from './pages/AuthPage'

const KEY_STORAGE = 'fgpt_api_key'
const JOB_STORAGE = 'fgpt_active_job'
const DEFAULT_QUERY =
  'Analyze the latest quarterly results and give a qualitative outlook for the next quarter.'
const POLL_MS = 3000

type View = 'landing' | 'auth' | 'app'
type Route = 'landing' | 'auth' | 'console' | 'sample'

function currentRoute(): Route {
  const h = window.location.hash.replace(/^#\/?/, '')
  if (h === 'sample' || h === 'console') return h
  if (h === 'auth') return 'auth'
  return 'landing'
}

function goRoute(route: Route) {
  const target = route === 'console' ? '#/console' : route === 'sample' ? '#/sample' : route === 'auth' ? '#/auth' : '#/'
  if (window.location.hash !== target) window.location.hash = target
}

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
  const [view, setView] = useState<View>('landing')
  const [session, setSession] = useState<SessionInfoLike | null>(null)
  const [apiKey, setApiKey] = useState(() => localStorage.getItem(KEY_STORAGE) ?? '')
  const [providerKey, setProviderKey] = useState(() => localStorage.getItem('fgpt_provider_key') ?? '')
  const [companies, setCompanies] = useState<Company[]>([])
  const [stats, setStats] = useState<Stats | null>(null)
  const [quota, setQuota] = useState<QuotaInfo | null>(null)
  const [job, setJob] = useState<Job | null>(null)
  const [sample, setSample] = useState(false)
  const [submitError, setSubmitError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [startedAt, setStartedAt] = useState(Date.now())
  const [history, setHistory] = useState<JobSummary[]>([])
  const [historyLoading, setHistoryLoading] = useState(false)
  const timer = useRef<number | null>(null)

  const auth: Auth | undefined = session
    ? { token: session.token, providerKey: providerKey || undefined }
    : apiKey.trim()
      ? { apiKey, providerKey: providerKey || undefined }
      : undefined

  useEffect(() => {
    fetchCompanies().then(setCompanies).catch(() => {})
    fetchStats().then(setStats).catch(() => {})
  }, [])

  useEffect(() => {
    localStorage.setItem(KEY_STORAGE, apiKey)
  }, [apiKey])

  useEffect(() => {
    localStorage.setItem('fgpt_provider_key', providerKey)
  }, [providerKey])

  // Supabase session lifecycle (no-op when auth isn't configured).
  useEffect(() => {
    if (!supabase) return
    supabase.auth.getSession().then(({ data }) => {
      const s = data.session
      if (s?.user.email) setSession({ email: s.user.email, token: s.access_token })
    })
    const { data } = supabase.auth.onAuthStateChange((_event, s) => {
      if (s?.user.email) setSession({ email: s.user.email, token: s.access_token })
      else setSession(null)
    })
    return () => data.subscription.unsubscribe()
  }, [])

  const stopPolling = useCallback(() => {
    if (timer.current !== null) {
      window.clearInterval(timer.current)
      timer.current = null
    }
  }, [])

  useEffect(() => stopPolling, [stopPolling])

  const applyRoute = useCallback(
    (route: Route) => {
      if (route === 'sample') {
        // 'sample' route preloads the console with the sample report.
        stopPolling()
        setSample(true)
        setSubmitError(null)
        setJob(sampleJob as unknown as Job)
        setView('app')
      } else if (route === 'console') {
        // Console guard: no session and no key → sign in first.
        if (!session && !apiKey.trim() && !loadActiveJob()) {
          setView('auth')
        } else {
          setView('app')
        }
      } else if (route === 'auth') {
        setView(session ? 'app' : 'auth')
      } else {
        setView('landing')
      }
    },
    [session, apiKey, stopPolling],
  )

  const refreshHistory = useCallback(async () => {
    if (!auth) return
    setHistoryLoading(true)
    try {
      setHistory(await listForecasts(auth))
    } catch {
      /* history is best-effort */
    } finally {
      setHistoryLoading(false)
    }
  }, [auth])

  const refreshQuota = useCallback(async () => {
    if (!auth) return
    try {
      setQuota(await fetchQuotaMe(auth))
    } catch {
      /* quota chip is best-effort */
    }
  }, [auth])

  useEffect(() => {
    if (auth) refreshQuota()
  }, [auth, refreshQuota])

  const poll = useCallback(
    (jobId: number) => {
      stopPolling()
      timer.current = window.setInterval(async () => {
        try {
          const next = await getForecast(auth!, jobId)
          setJob(next)
          saveActiveJob(
            next.status === 'completed' || next.status === 'failed'
              ? null
              : { jobId, status: next.status },
          )
          if (next.status === 'completed' || next.status === 'failed') {
            stopPolling()
            refreshHistory()
            refreshQuota()
          }
        } catch (e) {
          const err = e as Error & { status?: number }
          if (err.status === 429) return
          setSubmitError(err.message)
          stopPolling()
          saveActiveJob(null)
        }
      }, POLL_MS)
    },
    [auth, stopPolling, refreshHistory, refreshQuota],
  )

  // Resume an in-flight job after a refresh, or honour the current route.
  useEffect(() => {
    const active = loadActiveJob()
    if (active && (localStorage.getItem(KEY_STORAGE) || supabase)) {
      setView('app')
      setStartedAt(Date.now())
      setJob({ job_id: active.jobId, status: active.status as Job['status'] })
      poll(active.jobId)
    } else {
      applyRoute(currentRoute())
    }
    const onHashChange = () => applyRoute(currentRoute())
    window.addEventListener('hashchange', onHashChange)
    return () => window.removeEventListener('hashchange', onHashChange)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    if (view === 'app' && auth) refreshHistory()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [view])

  const onSubmit = useCallback(
    async (company: string, query: string) => {
      setSubmitError(null)
      setSample(false)
      setSubmitting(true)
      stopPolling()
      setJob(null)
      setStartedAt(Date.now())
      try {
        const resp = await submitForecast(auth!, { company, query })
        setJob({ job_id: resp.job_id, status: resp.status })
        saveActiveJob({ jobId: resp.job_id, status: resp.status })
        poll(resp.job_id)
        refreshHistory()
        refreshQuota()
      } catch (e) {
        setSubmitError((e as Error).message)
      } finally {
        setSubmitting(false)
      }
    },
    [auth, poll, stopPolling, refreshHistory, refreshQuota],
  )

  const onOpenHistory = useCallback(
    async (jobId: number) => {
      try {
        setSample(false)
        setJob(await getForecast(auth!, jobId))
      } catch (e) {
        setSubmitError((e as Error).message)
      }
    },
    [auth],
  )

  const onSample = useCallback(() => {
    applyRoute('sample')
    goRoute('sample')
  }, [applyRoute])

  const onReset = useCallback(() => {
    stopPolling()
    setJob(null)
    setSample(false)
    setSubmitError(null)
    saveActiveJob(null)
    applyRoute('console')
    goRoute('console')
  }, [stopPolling, applyRoute])

  const navTo = useCallback(
    (v: 'landing' | 'app' | 'auth') => {
      const route: Route = v === 'app' ? 'console' : v
      applyRoute(route)
      goRoute(route)
    },
    [applyRoute],
  )

  const onSignOut = useCallback(() => {
    if (supabase) supabase.auth.signOut()
    setSession(null)
  }, [])

  const showResult = (job?.status === 'completed' || sample) && job?.result
  const showTimeline =
    job && !showResult && (job.status === 'queued' || job.status === 'running' || job.status === 'failed')

  return (
    <div className="shell">
      <Nav
        view={view}
        onNav={navTo}
        quota={quota}
        signedInEmail={session?.email ?? null}
        onSignOut={onSignOut}
      />

      {view === 'landing' && (
        <Landing
          stats={stats}
          onSample={onSample}
          onLaunch={() => navTo('app')}
          onAuth={() => navTo('auth')}
        />
      )}

      {view === 'auth' && (
        <AuthPage session={session} onSession={setSession} onReady={() => navTo('app')} />
      )}

      {view === 'app' && (
        <div className="console">
          <div className="console-main">
            {!showResult && (
              <SubmitForm
                apiKey={apiKey}
                onApiKeyChange={setApiKey}
                hideKeyField={Boolean(session)}
                providerKey={providerKey}
                onProviderKeyChange={setProviderKey}
                companies={companies}
                defaultQuery={DEFAULT_QUERY}
                submitting={submitting}
                onSubmit={onSubmit}
              />
            )}

            {submitError && <div className="banner error fade-up">{submitError}</div>}

            {showTimeline && job && <JobTimeline job={job} startedAt={startedAt} onCancel={onReset} />}

            {showResult && job?.result && (
              <ResultView job={job} result={job.result} sample={sample} onReset={onReset} />
            )}
          </div>

          <HistoryPanel
            summaries={history}
            loading={historyLoading}
            activeJobId={job?.job_id ?? null}
            onOpen={onOpenHistory}
            onRefresh={refreshHistory}
          />
        </div>
      )}

      <Footer onNav={navTo} />
    </div>
  )
}

// Local structural type (AuthPanel owns its real one) to avoid circular import.
interface SessionInfoLike {
  email: string
  token: string
}
