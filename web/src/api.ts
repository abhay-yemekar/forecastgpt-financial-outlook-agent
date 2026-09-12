import type { Company, Job, JobSummary, Stats, SubmitResponse } from './types'

// The web app is just another client of the public /forecasts contract.
// Auth: either a Supabase session token (console users, quota'd) or an
// API key (developers, unlimited). Optionally a BYOK provider key rides
// along to bypass quota.

export interface Auth {
  apiKey?: string
  token?: string
  providerKey?: string
}

function authHeaders(auth?: Auth): Record<string, string> {
  const h: Record<string, string> = { 'Content-Type': 'application/json' }
  if (auth?.token) h['Authorization'] = `Bearer ${auth.token}`
  else if (auth?.apiKey) h['X-API-Key'] = auth.apiKey
  if (auth?.providerKey) h['X-Provider-Key'] = auth.providerKey
  return h
}

async function request<T>(path: string, auth: Auth | undefined, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, { ...init, headers: { ...authHeaders(auth), ...(init?.headers ?? {}) } })
  const body = await resp.json().catch(() => null)
  if (!resp.ok) {
    const detail = body?.detail ?? `Request failed (${resp.status})`
    const err = new Error(typeof detail === 'string' ? detail : JSON.stringify(detail)) as Error & {
      status?: number
    }
    err.status = resp.status
    throw err
  }
  return body as T
}

export function fetchCompanies(): Promise<Company[]> {
  return fetch('/companies').then((r) => {
    if (!r.ok) throw new Error(`Could not load companies (${r.status})`)
    return r.json() as Promise<Company[]>
  })
}

export function fetchStats(): Promise<Stats> {
  return fetch('/stats').then((r) => {
    if (!r.ok) throw new Error(`Could not load stats (${r.status})`)
    return r.json() as Promise<Stats>
  })
}

export interface QuotaInfo {
  quota: 'free_tier' | 'unlimited'
  kind: 'user' | 'api_key'
  email?: string
  used?: number
  limit?: number
  global_used?: number
  global_limit?: number
  resets_at?: string
}

export function fetchQuotaMe(auth: Auth): Promise<QuotaInfo> {
  return request<QuotaInfo>('/quota/me', auth)
}

export function listForecasts(auth: Auth, company?: string): Promise<JobSummary[]> {
  const qs = company ? `?company=${encodeURIComponent(company)}` : ''
  return request<JobSummary[]>(`/forecasts${qs}`, auth)
}

export function submitForecast(
  auth: Auth,
  body: { company: string; query: string },
): Promise<SubmitResponse> {
  return request<SubmitResponse>('/forecasts', auth, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getForecast(auth: Auth, jobId: number): Promise<Job> {
  return request<Job>(`/forecasts/${jobId}`, auth)
}
