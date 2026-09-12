import { useEffect, useState } from 'react'
import { useCountUp } from '../useCountUp'
import { fmtElapsed } from '../format'

/** Animated product mock for the hero: a stylized forecast report card
 * with bars that grow on mount and a live-feeling elapsed timer. */
export default function HeroMock() {
  const [mounted, setMounted] = useState(false)
  const [seconds, setSeconds] = useState(247)
  useEffect(() => {
    const t = window.setTimeout(() => setMounted(true), 150)
    const tick = window.setInterval(() => setSeconds((s) => s + 1), 1000)
    return () => {
      window.clearTimeout(t)
      window.clearInterval(tick)
    }
  }, [])

  const revenue = useCountUp(mounted ? 64479 : 0, 1200)
  const margin = useCountUp(mounted ? 24.5 : 0, 1400)

  return (
    <div className="hero-mock glass" aria-hidden="true">
      <div className="mock-head">
        <span className="mock-dot" />
        <span className="mock-dot" />
        <span className="mock-dot" />
        <span className="mock-title mono">forecast · TCS · Q-next</span>
        <span className="mock-elapsed mono">{fmtElapsed(0, seconds * 1000)}</span>
      </div>

      <div className="mock-body">
        <div className="mock-metrics">
          <div className="mock-metric">
            <span className="mock-label">Revenue</span>
            <strong className="mono">{Math.round(revenue).toLocaleString('en-IN')} ₹cr</strong>
            <div className="mock-bar">
              <span style={{ width: mounted ? '78%' : '6%' }} />
            </div>
          </div>
          <div className="mock-metric">
            <span className="mock-label">Margin</span>
            <strong className="mono">{margin.toFixed(1)}%</strong>
            <div className="mock-bar">
              <span style={{ width: mounted ? '54%' : '6%' }} />
            </div>
          </div>
          <div className="mock-metric">
            <span className="mock-label">Confidence</span>
            <strong className="mono mock-good">MEDIUM</strong>
            <div className="mock-bar">
              <span style={{ width: mounted ? '62%' : '6%' }} className="good" />
            </div>
          </div>
        </div>

        <div className="mock-lines">
          <span style={{ width: '96%' }} />
          <span style={{ width: '88%' }} />
          <span style={{ width: '92%' }} />
          <span style={{ width: '74%' }} />
          <span style={{ width: '84%' }} className="alt" />
        </div>

        <div className="mock-cite">
          <span className="mono">§ p.14 — results deck</span>
          <span className="mono">§ p.6 — earnings call</span>
        </div>
      </div>

      <div className="mock-shimmer" />
    </div>
  )
}
