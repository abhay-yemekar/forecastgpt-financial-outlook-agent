import { useEffect, useState } from 'react'

const LEVELS: Record<string, { frac: number; color: string }> = {
  high: { frac: 0.92, color: '#34d399' },
  medium: { frac: 0.62, color: '#fbbf24' },
  low: { frac: 0.3, color: '#f87171' },
}

const ARC_LENGTH = Math.PI * 50 // semicircle, r = 50

export default function ConfidenceGauge({ level }: { level?: string }) {
  const key = (level ?? 'unknown').toLowerCase()
  const conf = LEVELS[key] ?? LEVELS.low
  const [mounted, setMounted] = useState(false)
  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 80)
    return () => window.clearTimeout(t)
  }, [])

  const offset = mounted ? ARC_LENGTH * (1 - conf.frac) : ARC_LENGTH

  return (
    <div className="gauge">
      <svg viewBox="0 0 120 72" width="132" height="80" aria-label={`confidence ${key}`}>
        <defs>
          <linearGradient id="gauge-grad" x1="0" y1="0" x2="1" y2="0">
            <stop offset="0%" stopColor="#8b5cf6" />
            <stop offset="100%" stopColor="#22d3ee" />
          </linearGradient>
        </defs>
        <path
          d="M 10 62 A 50 50 0 0 1 110 62"
          fill="none"
          stroke="rgba(255,255,255,0.09)"
          strokeWidth="9"
          strokeLinecap="round"
        />
        <path
          d="M 10 62 A 50 50 0 0 1 110 62"
          fill="none"
          stroke="url(#gauge-grad)"
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={ARC_LENGTH}
          strokeDashoffset={offset}
          style={{ transition: 'stroke-dashoffset 1.1s cubic-bezier(0.22, 0.8, 0.3, 1)' }}
        />
        <text
          x="60"
          y="52"
          textAnchor="middle"
          fontSize="17"
          fontWeight="700"
          fill={conf.color}
          fontFamily="inherit"
        >
          {key.toUpperCase()}
        </text>
        <text x="60" y="68" textAnchor="middle" fontSize="8" fill="#6b7490" letterSpacing="1.5">
          CONFIDENCE
        </text>
      </svg>
    </div>
  )
}
