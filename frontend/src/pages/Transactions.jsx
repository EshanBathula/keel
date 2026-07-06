import { useEffect, useRef, useState } from 'react'
import { api, fmtMoney } from '../lib/api.js'

const emptyForm = () => ({
  type: 'income', amount: '', category: '', description: '',
  date: new Date().toISOString().slice(0, 10), customer_id: '',
})

export default function Transactions() {
  const [txs, setTxs] = useState(null)
  const [customers, setCustomers] = useState([])
  const [form, setForm] = useState(emptyForm())
  const [error, setError] = useState('')
  const [importResult, setImportResult] = useState(null)
  const fileRef = useRef()

  const load = () => {
    Promise.all([api('/api/transactions'), api('/api/customers')])
      .then(([t, c]) => { setTxs(t); setCustomers(c) })
      .catch((e) => setError(e.message))
  }
  useEffect(load, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/api/transactions', {
        method: 'POST',
        body: {
          type: form.type,
          amount: Number(form.amount),
          category: form.category || 'Uncategorized',
          description: form.description,
          date: form.date,
          customer_id: form.customer_id ? Number(form.customer_id) : null,
        },
      })
      setForm(emptyForm())
      load()
    } catch (err) { setError(err.message) }
  }

  const remove = async (id) => {
    await api(`/api/transactions/${id}`, { method: 'DELETE' })
    load()
  }

  const importCsv = async (e) => {
    const file = e.target.files?.[0]
    if (!file) return
    const fd = new FormData()
    fd.append('file', file)
    try {
      const res = await api('/api/transactions/import', { method: 'POST', formData: fd })
      setImportResult(res)
      load()
    } catch (err) { setError(err.message) }
    finally { if (fileRef.current) fileRef.current.value = '' }
  }

  const customerName = (id) => customers.find((c) => c.id === id)?.name || ''

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Transactions</h1>
          <div className="sub">Every dollar in and out</div>
        </div>
        <div>
          <button className="btn ghost" onClick={() => fileRef.current?.click()}>Import CSV</button>
          <input ref={fileRef} type="file" accept=".csv" hidden onChange={importCsv} />
        </div>
      </div>

      {importResult && (
        <div className="card" style={{ marginBottom: 14 }}>
          Imported {importResult.created} transactions.
          {importResult.errors.length > 0 && (
            <span className="down"> {importResult.errors.length} rows skipped: {importResult.errors.slice(0, 3).join('; ')}</span>
          )}
          <div className="muted">CSV columns: date, type (income/expense), amount, category, description</div>
        </div>
      )}

      <div className="card" style={{ marginBottom: 14 }}>
        <form className="form-row" onSubmit={submit}>
          <label>Type
            <select value={form.type} onChange={(e) => setForm({ ...form, type: e.target.value })}>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
            </select>
          </label>
          <label>Amount
            <input type="number" step="0.01" min="0.01" required value={form.amount}
              onChange={(e) => setForm({ ...form, amount: e.target.value })} />
          </label>
          <label>Category
            <input value={form.category} placeholder="Services"
              onChange={(e) => setForm({ ...form, category: e.target.value })} />
          </label>
          <label>Date
            <input type="date" required value={form.date}
              onChange={(e) => setForm({ ...form, date: e.target.value })} />
          </label>
          <label>Customer
            <select value={form.customer_id} onChange={(e) => setForm({ ...form, customer_id: e.target.value })}>
              <option value="">—</option>
              {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
            </select>
          </label>
          <label style={{ flex: 1, minWidth: 160 }}>Description
            <input value={form.description} onChange={(e) => setForm({ ...form, description: e.target.value })} />
          </label>
          <button className="btn">Add</button>
        </form>
        {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      <div className="card">
        {!txs ? <div className="muted">Loading…</div> : txs.length === 0 ? (
          <div className="empty">No transactions yet. Add one above or import a CSV to get started.</div>
        ) : (
          <table>
            <thead>
              <tr><th>Date</th><th>Type</th><th>Category</th><th>Description</th><th>Customer</th>
                <th style={{ textAlign: 'right' }}>Amount</th><th /></tr>
            </thead>
            <tbody>
              {txs.map((t) => (
                <tr key={t.id}>
                  <td className="num">{t.date}</td>
                  <td><span className={`pill ${t.type}`}>{t.type}</span></td>
                  <td>{t.category}</td>
                  <td className="muted">{t.description}</td>
                  <td>{customerName(t.customer_id)}</td>
                  <td className={`num ${t.type === 'income' ? 'up' : ''}`} style={{ textAlign: 'right' }}>
                    {t.type === 'expense' ? '−' : ''}{fmtMoney(t.amount)}
                  </td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn danger small" onClick={() => remove(t.id)}>Delete</button>
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
