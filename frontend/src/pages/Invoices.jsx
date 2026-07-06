import { useEffect, useState } from 'react'
import { api, fmtMoney } from '../lib/api.js'

const today = () => new Date().toISOString().slice(0, 10)
const plus30 = () => new Date(Date.now() + 30 * 864e5).toISOString().slice(0, 10)

export default function Invoices() {
  const [invoices, setInvoices] = useState(null)
  const [customers, setCustomers] = useState([])
  const [form, setForm] = useState({ number: '', amount: '', customer_id: '', issue_date: today(), due_date: plus30(), status: 'sent' })
  const [error, setError] = useState('')

  const load = () => {
    Promise.all([api('/api/invoices'), api('/api/customers')])
      .then(([i, c]) => { setInvoices(i); setCustomers(c) })
      .catch((e) => setError(e.message))
  }
  useEffect(load, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/api/invoices', {
        method: 'POST',
        body: { ...form, amount: Number(form.amount), customer_id: form.customer_id ? Number(form.customer_id) : null },
      })
      setForm({ number: '', amount: '', customer_id: '', issue_date: today(), due_date: plus30(), status: 'sent' })
      load()
    } catch (err) { setError(err.message) }
  }

  const setStatus = async (id, status) => {
    await api(`/api/invoices/${id}`, { method: 'PATCH', body: { status } })
    load()
  }

  const customerName = (id) => customers.find((c) => c.id === id)?.name || '—'

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Invoices</h1>
          <div className="sub">Marking an invoice paid records the revenue automatically</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <form className="form-row" onSubmit={submit}>
          <label>Number
            <input required value={form.number} placeholder="INV-1006"
              onChange={(e) => setForm({ ...form, number: e.target.value })} />
          </label>
          <label>Amount
            <input type="number" step="0.01" min="0.01" required value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </label>
          <label>Customer
            <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
              <option value="">—</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label>Issued
            <input type="date" required value={form.issue_date}
              onChange={(e) => setForm({ ...form, issue_date: e.target.value })} />
          </label>
          <label>Due
            <input type="date" required value={form.due_date}
              onChange={(e) => setForm({ ...form, due_date: e.target.value })} />
          </label>
          <button className="btn">Create invoice</button>
        </form>
        {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      <div className="card">
        {!invoices ? <div className="muted">Loading…</div> : invoices.length === 0 ? (
          <div className="empty">No invoices yet. Create one above to start tracking receivables.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Number</th><th>Customer</th><th>Issued</th><th>Due</th><th>Status</th>
                <th style={{ textAlign: 'right' }}>Amount</th><th /></tr>
            </thead>
            <tbody>
              {invoices.map((inv) => (
                <tr key={inv.id}>
                  <td className="num">{inv.number}</td>
                  <td>{customerName(inv.customer_id)}</td>
                  <td className="num">{inv.issue_date}</td>
                  <td className="num">{inv.due_date}</td>
                  <td><span className={`pill ${inv.status}`}>{inv.status}</span></td>
                  <td className="num" style={{ textAlign: 'right' }}>{fmtMoney(inv.amount)}</td>
                  <td style={{ textAlign: 'right' }}>
                    {inv.status !== 'paid' && (
                      <button className="btn small" onClick={() => setStatus(inv.id, 'paid')}>Mark paid</button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </>
  )
}
