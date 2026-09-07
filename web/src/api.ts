import type { Company, Job, JobSummary, Stats, SubmitResponse } from './types'

// The web app is just another client of the public /forecasts contract —
// same endpoints, same API key, no special backend path.

async function request<T>(path: string, apiKey: string, init?: RequestInit): Promise<T> {
  const resp = await fetch(path, {
    ...init,
    headers: {
      'Content-Type': 'application/json',
      'X-API-Key': apiKey,
      ...(init?.headers ?? {}),
    },
  })
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
  // /companies is intentionally open — no key needed.
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

export function listForecasts(apiKey: string, company?: string): Promise<JobSummary[]> {
  const qs = company ? `?company=${encodeURIComponent(company)}` : ''
  return request<JobSummary[]>(`/forecasts${qs}`, apiKey)
}

export function submitForecast(
  apiKey: string,
  body: { company: string; query: string },
): Promise<SubmitResponse> {
  return request<SubmitResponse>('/forecasts', apiKey, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

export function getForecast(apiKey: string, jobId: number): Promise<Job> {
  return request<Job>(`/forecasts/${jobId}`, apiKey)
}
