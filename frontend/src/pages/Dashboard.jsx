import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Bar, Line, XAxis, YAxis, Tooltip,
  CartesianGrid, PieChart, Pie, Cell,
} from 'recharts'
import { api, fmtMoney, fmtMonth } from '../lib/api.js'

const PIE_COLORS = ['#14535c', '#2d7a86', '#c08a2d', '#7a9aa4', '#43575f', '#a8bfc6', '#d9c48f']

function Waterline({ score, grade }) {
  return (
    <div className="card waterline" style={{ minHeight: 148 }}>
      <div className="kpi-label">Financial health</div>
      <div className="score-big">
        {score}<span style={{ fontSize: 20, color: 'var(--ink-soft)' }}>/100</span>{' '}
        <span className="grade">{grade}</span>
      </div>
      <div className="muted" style={{ position: 'relative', zIndex: 2 }}>
        Profitability, growth, collections & runway
      </div>
      <div className="water" style={{ height: `${score}%` }} />
    </div>
  )
}

function Kpi({ label, value, delta, deltaLabel }) {
  return (
    <div className="card">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num">{value}</div>
      {delta != null && (
        <div className={`kpi-delta ${delta >= 0 ? 'up' : 'down'}`}>
          {delta >= 0 ? '▲' : '▼'} {Math.abs(delta)}% {deltaLabel}
        </div>
      )}
    </div>
  )
}

export default function Dashboard() {
  const [kpis, setKpis] = useState(null)
  const [monthly, setMonthly] = useState([])
  const [categories, setCategories] = useState([])
  const [topCustomers, setTopCustomers] = useState([])
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([
      api('/api/analytics/kpis'),
      api('/api/analytics/monthly?months=12'),
      api('/api/analytics/categories?type=expense&months=6'),
      api('/api/analytics/top-customers?limit=5'),
    ]).then(([k, m, c, t]) => {
      setKpis(k)
      setMonthly(m.map((p) => ({ ...p, label: fmtMonth(p.month) })))
      setCategories(c.slice(0, 7))
      setTopCustomers(t)
    }).catch((e) => setError(e.message))
  }, [])

  if (error) return <div className="card">Couldn’t load the dashboard: {error}</div>
  if (!kpis) return <div className="muted">Loading…</div>

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Dashboard</h1>
          <div className="sub">Where the business stands this month</div>
        </div>
      </div>

      <div className="grid kpi-grid">
        <Waterline score={kpis.health_score} grade={kpis.health_grade} />
        <Kpi label="Revenue this month" value={fmtMoney(kpis.revenue_this_month)}
          delta={kpis.revenue_growth_pct} deltaLabel="vs last month" />
        <Kpi label="Net profit" value={fmtMoney(kpis.net_this_month)}
          delta={kpis.profit_margin_pct} deltaLabel="margin" />
        <Kpi label="Cash runway" value={kpis.cash_runway_months != null ? `${kpis.cash_runway_months} mo` : '—'} />
        <Kpi label="Overdue receivables" value={fmtMoney(kpis.overdue_receivables)} />
      </div>

      <div className="grid two-col">
        <div className="card">
          <h2>Revenue vs. expenses — trailing 12 months</h2>
          <div style={{ height: 280, marginTop: 12 }}>
            <ResponsiveContainer>
              <ComposedChart data={monthly}>
                <CartesianGrid stroke="#eef2f3" vertical={false} />
                <XAxis dataKey="label" tick={{ fontSize: 12 }} />
                <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
                <Tooltip formatter={(v) => fmtMoney(v)} />
                <Bar dataKey="revenue" name="Revenue" fill="#14535c" radius={[3, 3, 0, 0]} />
                <Bar dataKey="expenses" name="Expenses" fill="#c9d6d9" radius={[3, 3, 0, 0]} />
                <Line dataKey="net" name="Net" stroke="#c08a2d" strokeWidth={2} dot={false} />
              </ComposedChart>
            </ResponsiveContainer>
          </div>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: 14 }}>
          <div className="card">
            <h2>Where money goes (6 mo)</h2>
            {categories.length === 0 ? <div className="empty">No expenses yet</div> : (
              <div style={{ height: 180 }}>
                <ResponsiveContainer>
                  <PieChart>
                    <Pie data={categories} dataKey="total" nameKey="category"
                      innerRadius={45} outerRadius={72} paddingAngle={2}>
                      {categories.map((_, i) => <Cell key={i} fill={PIE_COLORS[i % PIE_COLORS.length]} />)}
                    </Pie>
                    <Tooltip formatter={(v) => fmtMoney(v)} />
                  </PieChart>
                </ResponsiveContainer>
              </div>
            )}
          </div>
          <div className="card">
            <h2>Top customers</h2>
            {topCustomers.length === 0 ? <div className="empty">Link transactions to customers to see this</div> : (
              <table>
                <tbody>
                  {topCustomers.map((c) => (
                    <tr key={c.customer_id}>
                      <td>{c.name}</td>
                      <td className="num" style={{ textAlign: 'right' }}>{fmtMoney(c.revenue)}</td>
                      <td className="muted num" style={{ textAlign: 'right', width: 56 }}>{c.share_pct}%</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>
        </div>
      </div>
    </>
  )
}
