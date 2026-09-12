import { useState } from 'react'
import Reveal from './Reveal'

const FAQS = [
  {
    q: 'What exactly do I get?',
    a: 'A narrative outlook report for the next quarter: revenue, net-profit and operating-margin direction with quarter-over-quarter numbers, management themes from earnings calls, risks, opportunities, and an overall confidence level — every number traceable to the filing it came from.',
  },
  {
    q: 'Is this just ChatGPT with a finance prompt?',
    a: 'No. Every report is grounded in real documents fetched from screener.in — results decks, fact sheets and earnings-call transcripts. The retrieval layer pulls the relevant passages, numeric extraction computes actual quarter-over-quarter deltas, and the model is instructed to refuse numbers it was not given.',
  },
  {
    q: 'Which companies are covered?',
    a: 'A curated registry of NSE-listed companies today — TCS, Infosys, HDFC Bank, Reliance and more. The registry grows one line at a time, and the document pipeline is built to extend to more sources.',
  },
  {
    q: 'Why does a forecast take minutes?',
    a: 'Because it does real work: it downloads the latest filings, extracts metrics from the PDFs, embeds and retrieves earnings-call passages, then reasons over everything. It runs asynchronously — you get a job id immediately and poll for the result. No browser tab babysitting a spinning wheel on a blocked HTTP call.',
  },
  {
    q: 'What does the free tier cost me?',
    a: 'Nothing. Sign in and you get a few forecasts per day on us. Need more? Paste your own provider key (BYOK) and the quota disappears — your key never touches our database.',
  },
  {
    q: 'Can I use it without the website?',
    a: 'Yes — the website is just another client. Create an API key with the CLI and call the same /forecasts endpoint the console uses. Same auth, same rate limits, same JSON.',
  },
]

export default function Faq() {
  const [open, setOpen] = useState<number | null>(0)
  return (
    <div className="faq">
      {FAQS.map((f, i) => (
        <Reveal key={f.q} delay={(i % 3) * 60}>
          <div className={`faq-item ${open === i ? 'open' : ''}`}>
            <button className="faq-q" onClick={() => setOpen(open === i ? null : i)} aria-expanded={open === i}>
              {f.q}
              <span className="faq-caret">{open === i ? '−' : '+'}</span>
            </button>
            <div className="faq-a" style={{ maxHeight: open === i ? 320 : 0 }}>
              <p className="muted">{f.a}</p>
            </div>
          </div>
        </Reveal>
      ))}
    </div>
  )
}
