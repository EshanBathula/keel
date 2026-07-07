import { useEffect, useState } from 'react'
import {
  ResponsiveContainer, ComposedChart, Area, Line, XAxis, YAxis, Tooltip, CartesianGrid,
  ReferenceLine,
} from 'recharts'
import { api, fmtMoney, fmtMonth, roundToCents } from '../lib/api.js'

const fmtWeek = (iso) => {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d).toLocaleString('en-US', { month: 'short', day: 'numeric' })
}

const MODEL_LABELS = {
  seasonal_naive: 'seasonal pattern',
  damped_trend: 'damped trend',
  ols_ma_blend: 'trend + average blend',
}

function Stat({ label, value, sub, tone }) {
  return (
    <div className="card">
      <div className="kpi-label">{label}</div>
      <div className={`kpi-value num ${tone || ''}`}>{value}</div>
      {sub && <div className="muted" style={{ fontSize: 13 }}>{sub}</div>}
    </div>
  )
}

const emptyScenario = () => ({ revenue_pct: '', expense: '', start_month: '' })

export default function Forecast() {
  const [data, setData] = useState(null)         // currently displayed forecast (base or scenario)
  const [baseline, setBaseline] = useState(null) // always the no-scenario forecast
  const [horizon, setHorizon] = useState(6)
  const [scenario, setScenario] = useState(emptyScenario())
  const [scenarioActive, setScenarioActive] = useState(false)
  const [error, setError] = useState('')
  const [scenarioError, setScenarioError] = useState('')

  useEffect(() => {
    setData(null)
    setScenarioActive(false)
    api(`/api/analytics/forecast?horizon=${horizon}`)
      .then((f) => { setBaseline(f); setData(f) })
      .catch((e) => setError(e.message))
  }, [horizon])

  const runScenario = async (e) => {
    e.preventDefault()
    setScenarioError('')
    const body = {}
    if (scenario.revenue_pct !== '') body.monthly_revenue_change_pct = Number(scenario.revenue_pct)
    if (scenario.expense !== '') {
      if (!scenario.start_month) { setScenarioError('Pick a start month for the new expense.'); return }
      body.new_monthly_expense_cents = Math.round(roundToCents(Number(scenario.expense)) * 100)
      body.start_month = scenario.start_month
    }
    if (Object.keys(body).length === 0) { setScenarioError('Set at least one change to model.'); return }
    try {
      const f = await api(`/api/analytics/scenario?horizon=${horizon}`, { method: 'POST', body })
      setData(f)
      setScenarioActive(true)
    } catch (err) { setScenarioError(err.message) }
  }

  const resetScenario = () => {
    setScenario(emptyScenario())
    setScenarioActive(false)
    setScenarioError('')
    setData(baseline)
  }

  if (error) return <div className="card">Couldn’t load the forecast: {error}</div>
  if (!data) return <div className="muted">Projecting…</div>

  const cashData = data.weekly.map((w, i) => ({
    ...w,
    label: fmtWeek(w.week_start),
    band: [w.cash_p10, w.cash_p90],
    baseline_p50: baseline && baseline.weekly[i] ? baseline.weekly[i].cash_p50 : null,
  }))
  const alert = data.cash_low_alert

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Cash-flow forecast</h1>
          <div className="sub">
            {data.expected_error_pct != null
              ? <>Backtested weekly — typically within ±{data.expected_error_pct}% ({MODEL_LABELS[data.model_revenue] || data.model_revenue})</>
              : 'Backtested weekly projection'}
          </div>
        </div>
        <label>
          Horizon
          <select value={horizon} onChange={(e) => setHorizon(Number(e.target.value))}>
            {[3, 6, 9, 12].map((h) => <option key={h} value={h}>{h} months</option>)}
          </select>
        </label>
      </div>

      {data.caveat && (
        <div className="card" style={{ marginBottom: 14, borderLeft: '4px solid #c08a2d' }}>
          <strong>Take this with a grain of salt.</strong> {data.caveat}
        </div>
      )}

      {alert && (
        <div className="card" style={{ marginBottom: 14, borderLeft: '4px solid #b3402e' }}>
          <strong className="down">Cash low warning.</strong>{' '}
          In a pessimistic (1-in-10) scenario, cash drops {fmtMoney(alert.shortfall)} below a one-month
          expense buffer in the week of {fmtWeek(alert.week_start)}. Collect receivables and defer
          discretionary spend before then.
        </div>
      )}

      <div className="grid kpi-grid" style={{ marginBottom: 14 }}>
        <Stat label="Safe to spend today" value={fmtMoney(data.safe_to_spend)}
          sub="Largest one-time purchase that keeps a one-month buffer for the next 90 days"
          tone={data.safe_to_spend > 0 ? 'up' : 'down'} />
        <Stat label="Lowest projected balance" value={fmtMoney(data.min_cash_balance)}
          sub={`Expected ${fmtWeek(data.min_cash_balance_date)}`}
          tone={data.min_cash_balance < 0 ? 'down' : ''} />
        <Stat label="Forecast accuracy" value={data.expected_error_pct != null ? `±${data.expected_error_pct}%` : '—'}
          sub={data.expected_error_pct != null ? 'Typical weekly error in backtests on your own data' : 'Not enough history to backtest yet'} />
      </div>

      <div className="card">
        <h2>Projected cash balance {scenarioActive && <span className="pill" style={{ marginLeft: 8 }}>scenario</span>}</h2>
        <div className="muted" style={{ fontSize: 13 }}>
          Shaded band: likely range (P10–P90) from backtest errors. Includes expected payments from unpaid invoices.
        </div>
        <div style={{ height: 320, marginTop: 12 }}>
          <ResponsiveContainer>
            <ComposedChart data={cashData}>
              <CartesianGrid stroke="#eef2f3" vertical={false} />
              <XAxis dataKey="label" tick={{ fontSize: 12 }} />
              <YAxis tick={{ fontSize: 12 }} tickFormatter={(v) => `$${(v / 1000).toFixed(0)}k`} />
              <Tooltip formatter={(v, name) =>
                Array.isArray(v) ? [`${fmtMoney(v[0])} – ${fmtMoney(v[1])}`, 'Likely range'] : [fmtMoney(v), name]} />
              <ReferenceLine y={0} stroke="#b3402e" strokeDasharray="4 4" />
              <Area dataKey="band" name="Likely range" stroke="none" fill="#14535c" fillOpacity={0.12} />
              {scenarioActive && (
                <Line dataKey="baseline_p50" name="Without changes" stroke="#7a9aa4"
                  strokeWidth={1.5} strokeDasharray="5 4" dot={false} />
              )}
              <Line dataKey="cash_p50" name="Expected cash" stroke="#14535c" strokeWidth={2} dot={false} />
            </ComposedChart>
          </ResponsiveContainer>
        </div>
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h2>What if…</h2>
        <form className="form-row" onSubmit={runScenario} style={{ marginTop: 10 }}>
          <label>Revenue change (%)
            <input type="number" step="1" placeholder="e.g. 10 or -15" value={scenario.revenue_pct}
              onChange={(e) => setScenario({ ...scenario, revenue_pct: e.target.value })} />
          </label>
          <label>New monthly expense ($)
            <input type="number" step="0.01" min="0" placeholder="e.g. 4000" value={scenario.expense}
              onChange={(e) => setScenario({ ...scenario, expense: e.target.value })} />
          </label>
          <label>Starting
            <input type="month" value={scenario.start_month}
              onChange={(e) => setScenario({ ...scenario, start_month: e.target.value })} />
          </label>
          <button className="btn">Model it</button>
          {scenarioActive && (
            <button type="button" className="btn ghost" onClick={resetScenario}>Reset</button>
          )}
        </form>
        {scenarioError && <div className="error" style={{ marginTop: 8 }}>{scenarioError}</div>}
      </div>

      <div className="card" style={{ marginTop: 14 }}>
        <h2>Monthly detail</h2>
        <table style={{ marginTop: 8 }}>
          <thead>
            <tr><th>Month</th><th>Revenue</th><th>Expenses</th><th>Net</th><th>Revenue range</th></tr>
          </thead>
          <tbody>
            {data.monthly.map((p) => (
              <tr key={p.month}>
                <td>{fmtMonth(p.month)}</td>
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
  )
}
