import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid,
} from 'recharts'
import { api, fmtMoney, fmtMonth } from '../lib/api.js'

export default function Forecast() {
  const [data, setData] = useState(null)
  const [horizon, setHorizon] = useState(6)
  const [error, setError] = useState('')

  useEffect(() => {
    api(`/api/analytics/forecast?horizon=${horizon}`)
      .then((f) => setData(f.map((p) => ({
        ...p,
        label: fmtMonth(p.month),
        band: [p.lower, p.upper],
      }))))
      .catch((e) => setError(e.message))
  }, [horizon])

  if (error) return <div className="card">Couldn’t load the forecast: {error}</div>

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Cash-flow forecast</h1>
          <div className="sub">Trend + moving-average projection with an ~80% confidence band</div>
        </div>
        <label>
          Horizon
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
            {[3, 6, 9, 12].map((h) => <option key={h} value={h}>{h} months</option>)}
          </select>
        </label>
      </div>

      {!data ? <div className="muted">Projecting…</div> : (
        <>
          <div className="card">
            <div style={{ height: 320 }}>
              <ResponsiveContainer>
                <ComposedChart data={data}>
                  <CartesianGrid stroke="#eef2f3" vertical={false} />
                  <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                  <Tooltip formatter={(v, name) =>
                    Array.isArray(v) ? [`${fmtMoney(v[0])} – ${fmtMoney(v[1])}`, 'Range'] : [fmtMoney(v), name]} />
                  <Area dataKey="band" name="Range" stroke="none" fill="#14535c" fillOpacity={0.12} />
                  <Line dataKey="projected_revenue" name="Projected revenue" stroke="#14535c" strokeWidth={2} />
                  <Line dataKey="projected_expenses" name="Projected expenses" stroke="#b3402e"
                    strokeWidth={2} strokeDasharray="5 4" dot={false} />
                  <Line dataKey="projected_net" name="Projected net" stroke="#c08a2d" strokeWidth={2} dot={false} />
                </ComposedChart>
              </ResponsiveContainer>
            </div>
          </div>
          <div className="card" style={{ marginTop: 14 }}>
            <table>
              <thead>
                <tr><th>Month</th><th>Revenue</th><th>Expenses</th><th>Net</th><th>Revenue range</th></tr>
              </thead>
              <tbody>
                {data.map((p) => (
                  <tr key={p.month}>
                    <td>{p.label}</td>
                    <td className="num">{fmtMoney(p.projected_revenue)}</td>
                    <td className="num">{fmtMoney(p.projected_expenses)}</td>
                    <td className={`num ${p.projected_net >= 0 ? 'up' : 'down'}`}>{fmtMoney(p.projected_net)}</td>
                    <td className="num muted">{fmtMoney(p.lower)} – {fmtMoney(p.upper)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}
    </>
  )
}
