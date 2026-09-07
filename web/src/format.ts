export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return ''
  const seconds = Math.floor((Date.now() - new Date(iso).getTime()) / 1000)
  if (seconds < 45) return 'just now'
  if (seconds < 3600) return `${Math.floor(seconds / 60)}m ago`
  if (seconds < 86400) return `${Math.floor(seconds / 3600)}h ago`
  return `${Math.floor(seconds / 86400)}d ago`
}

export function fmtElapsed(startedAt: number, now: number = Date.now()): string {
  const s = Math.max(0, Math.floor((now - startedAt) / 1000))
  const m = Math.floor(s / 60)
  return `${String(m).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`
}

export function fmtINR(value: number): string {
  return value.toLocaleString('en-IN')
}

export function parseMetricNum(v: string | null | undefined): number | null {
  if (v == null) return null
  const n = parseFloat(String(v).replace(/,/g, ''))
  return Number.isFinite(n) ? n : null
}
