import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'

export default function Insights() {
  const [insights, setInsights] = useState(null)
  const [error, setError] = useState('')

  useEffect(() => {
    api('/api/analytics/insights').then(setInsights).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="card">Couldn’t load insights: {error}</div>

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Insights</h1>
          <div className="sub">What to act on, in priority order</div>
        </div>
      </div>
      {!insights ? <div className="muted">Analyzing your books…</div> : insights.length === 0 ? (
        <div className="card empty">Add a few months of transactions and Keel will surface recommendations here.</div>
      ) : (
        <div className="grid" style={{ maxWidth: 760 }}>
          {insights.map((i) => (
            <div key={i.id} className={`card insight ${i.severity}`}>
              <div className="tag">{i.severity}</div>
              <h2 style={{ margin: '4px 0 6px' }}>{i.title}</h2>
              <p>{i.detail}</p>
              {i.estimated_impact && <div className="impact">Estimated impact: {i.estimated_impact}</div>}
            </div>
          ))}
        </div>
      )}
    </>
  )
}
