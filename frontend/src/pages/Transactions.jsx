import { useEffect, useRef, useState } from 'react'
import { api, fmtMoney, roundToCents } from '../lib/api.js'

const emptyForm = () => ({
  type: 'income', amount: '', category: '', description: '',
  date: new Date().toISOString().slice(0, 10), customer_id: '',
})

const emptyFilters = () => ({ type: '', q: '', date_from: '', date_to: '' })

const PAGE_SIZE = 25

export default function Transactions() {
  const [page, setPage] = useState(null) // { items, total, limit, offset }
  const [offset, setOffset] = useState(0)
  const [filters, setFilters] = useState(emptyFilters())
  const [customers, setCustomers] = useState([])
  const [form, setForm] = useState(emptyForm())
  const [error, setError] = useState('')
  const [importResult, setImportResult] = useState(null)
  const [editingId, setEditingId] = useState(null)
  const [editDraft, setEditDraft] = useState(null)
  const fileRef = useRef()

  const load = () => {
    const params = new URLSearchParams({ limit: PAGE_SIZE, offset })
    if (filters.type) params.set('type', filters.type)
    if (filters.q) params.set('q', filters.q)
    if (filters.date_from) params.set('date_from', filters.date_from)
    if (filters.date_to) params.set('date_to', filters.date_to)
    Promise.all([api(`/api/transactions?${params}`), api('/api/customers')])
      .then(([p, c]) => { setPage(p); setCustomers(c) })
      .catch((e) => setError(e.message))
  }
  useEffect(load, [offset, filters])

  const updateFilter = (patch) => {
    setOffset(0) // filters changed — start back at page 1
    setFilters((f) => ({ ...f, ...patch }))
  }

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/api/transactions', {
        method: 'POST',
        body: {
          type: form.type,
          amount: roundToCents(Number(form.amount)),
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

  const startEdit = (t) => {
    setEditingId(t.id)
    setEditDraft({
      type: t.type, amount: String(t.amount), category: t.category,
      description: t.description, date: t.date, customer_id: t.customer_id || '',
    })
  }
  const cancelEdit = () => { setEditingId(null); setEditDraft(null) }

  const saveEdit = async (id) => {
    setError('')
    try {
      await api(`/api/transactions/${id}`, {
        method: 'PATCH',
        body: {
          type: editDraft.type,
          amount: roundToCents(Number(editDraft.amount)),
          category: editDraft.category || 'Uncategorized',
          description: editDraft.description,
          date: editDraft.date,
          customer_id: editDraft.customer_id ? Number(editDraft.customer_id) : null,
        },
      })
      cancelEdit()
      load()
    } catch (err) { setError(err.message) }
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

  const total = page?.total ?? 0
  const rangeStart = total === 0 ? 0 : offset + 1
  const rangeEnd = Math.min(offset + PAGE_SIZE, total)

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

      <div className="card" style={{ marginBottom: 14 }}>
        <div className="form-row">
          <label>Type
            <select value={filters.type} onChange={(e) => updateFilter({ type: e.target.value })}>
              <option value="">All</option>
              <option value="income">Income</option>
              <option value="expense">Expense</option>
            </select>
          </label>
          <label>From
            <input type="date" value={filters.date_from}
              onChange={(e) => updateFilter({ date_from: e.target.value })} />
          </label>
          <label>To
            <input type="date" value={filters.date_to}
              onChange={(e) => updateFilter({ date_to: e.target.value })} />
          </label>
          <label style={{ flex: 1, minWidth: 200 }}>Search
            <input placeholder="Category or description…" value={filters.q}
              onChange={(e) => updateFilter({ q: e.target.value })} />
          </label>
          {(filters.type || filters.q || filters.date_from || filters.date_to) && (
            <button type="button" className="btn ghost small" onClick={() => updateFilter(emptyFilters())}>
              Clear filters
            </button>
          )}
        </div>
      </div>

      <div className="card">
        {!page ? <div className="muted">Loading…</div> : page.items.length === 0 ? (
          <div className="empty">
            {total === 0 && !filters.type && !filters.q && !filters.date_from && !filters.date_to
              ? 'No transactions yet. Add one above or import a CSV to get started.'
              : 'No transactions match these filters.'}
          </div>
        ) : (
          <>
            <table>
              <thead>
                <tr><th>Date</th><th>Type</th><th>Category</th><th>Description</th><th>Customer</th>
                  <th style={{ textAlign: 'right' }}>Amount</th><th /></tr>
              </thead>
              <tbody>
                {page.items.map((t) => editingId === t.id ? (
                  <tr key={t.id}>
                    <td><input type="date" value={editDraft.date}
                      onChange={(e) => setEditDraft({ ...editDraft, date: e.target.value })} /></td>
                    <td>
                      <select value={editDraft.type} onChange={(e) => setEditDraft({ ...editDraft, type: e.target.value })}>
                        <option value="income">Income</option>
                        <option value="expense">Expense</option>
                      </select>
                    </td>
                    <td><input value={editDraft.category}
                      onChange={(e) => setEditDraft({ ...editDraft, category: e.target.value })} /></td>
                    <td><input value={editDraft.description}
                      onChange={(e) => setEditDraft({ ...editDraft, description: e.target.value })} /></td>
                    <td>
                      <select value={editDraft.customer_id}
                        onChange={(e) => setEditDraft({ ...editDraft, customer_id: e.target.value })}>
                        <option value="">—</option>
                        {customers.map((c) => <option key={c.id} value={c.id}>{c.name}</option>)}
                      </select>
                    </td>
                    <td style={{ textAlign: 'right' }}>
                      <input type="number" step="0.01" min="0.01" style={{ width: 90, textAlign: 'right' }}
                        value={editDraft.amount}
                        onChange={(e) => setEditDraft({ ...editDraft, amount: e.target.value })} />
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button className="btn small" onClick={() => saveEdit(t.id)}>Save</button>{' '}
                      <button className="btn ghost small" onClick={cancelEdit}>Cancel</button>
                    </td>
                  </tr>
                ) : (
                  <tr key={t.id}>
                    <td className="num">{t.date}</td>
                    <td><span className={`pill ${t.type}`}>{t.type}</span></td>
                    <td>{t.category}</td>
                    <td className="muted">{t.description}</td>
                    <td>{customerName(t.customer_id)}</td>
                    <td className={`num ${t.type === 'income' ? 'up' : ''}`} style={{ textAlign: 'right' }}>
                      {t.type === 'expense' ? '−' : ''}{fmtMoney(t.amount)}
                    </td>
                    <td style={{ textAlign: 'right', whiteSpace: 'nowrap' }}>
                      <button className="btn ghost small" onClick={() => startEdit(t)}>Edit</button>{' '}
                      <button className="btn danger small" onClick={() => remove(t.id)}>Delete</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 12 }}>
              <span className="muted">Showing {rangeStart}–{rangeEnd} of {total}</span>
              <div>
                <button className="btn ghost small" disabled={offset === 0}
                  onClick={() => setOffset(Math.max(0, offset - PAGE_SIZE))}>Previous</button>{' '}
                <button className="btn ghost small" disabled={rangeEnd >= total}
                  onClick={() => setOffset(offset + PAGE_SIZE)}>Next</button>
              </div>
            </div>
          </>
        )}
      </div>
    </>
  )
}
