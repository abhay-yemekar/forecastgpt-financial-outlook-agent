export interface Company {
  symbol: string
  display_name: string
  exchange: string
}

export interface ForecastResult {
  company?: string
  period_analyzed?: string[]
  financial_trends?: {
    revenue?: string
    net_profit?: string
    operating_margin?: string
  }
  management_themes?: string[]
  risks?: string[]
  opportunities?: string[]
  qualitative_forecast_next_quarter?: string
  confidence?: { level?: string; reasons?: string[] }
  market_context?: { symbol?: string; price_inr?: number }
  financial_metrics?: FinancialMetrics
}

export interface FinancialMetrics {
  documents?: { path: string; metrics: Record<string, string | null> }[]
  trend_summary?: Record<string, unknown>
}

export type JobState = 'queued' | 'running' | 'completed' | 'failed'

export interface Job {
  job_id: number
  company?: string | null
  status: JobState
  created_at?: string | null
  result?: ForecastResult
  error?: string | null
}

export interface SubmitResponse {
  job_id: number
  status: JobState
  poll: string
}
