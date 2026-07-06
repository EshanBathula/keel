import { useEffect, useState } from 'react'
import { api } from '../lib/api.js'

export default function Customers() {
  const [customers, setCustomers] = useState(null)
  const [form, setForm] = useState({ name: '', email: '', notes: '' })
  const [error, setError] = useState('')

  const load = () => api('/api/customers').then(setCustomers).catch((e) => setError(e.message))
  useEffect(() => { load() }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    try {
      await api('/api/customers', { method: 'POST', body: form })
      setForm({ name: '', email: '', notes: '' })
      load()
    } catch (err) { setError(err.message) }
  }

  const remove = async (id) => {
    try {
      await api(`/api/customers/${id}`, { method: 'DELETE' })
      load()
    } catch (err) { setError(err.message) }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Customers</h1>
          <div className="sub">Link revenue to customers to unlock concentration and upsell insights</div>
        </div>
      </div>

      <div className="card" style={{ marginBottom: 14 }}>
        <form className="form-row" onSubmit={submit}>
          <label>Name
            <input required value={form.name} placeholder="Harbor Coffee Co."
              onChange={(e) => setForm({ ...form, name: e.target.value })} />
          </label>
          <label>Email
            <input type="email" value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label style={{ flex: 1, minWidth: 160 }}>Notes
            <input value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} />
          </label>
          <button className="btn">Add customer</button>
        </form>
        {error && <div className="error" style={{ marginTop: 8 }}>{error}</div>}
      </div>

      <div className="card">
        {!customers ? <div className="muted">Loading…</div> : customers.length === 0 ? (
          <div className="empty">No customers yet.</div>
        ) : (
          <table>
            <thead><tr><th>Name</th><th>Email</th><th>Notes</th><th /></tr></thead>
            <tbody>
              {customers.map((c) => (
                <tr key={c.id}>
                  <td>{c.name}</td>
                  <td className="muted">{c.email}</td>
                  <td className="muted">{c.notes}</td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn danger small" onClick={() => remove(c.id)}>Delete</button>
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
