import { useEffect, useState } from 'react'
import { api, auth } from '../lib/api.js'

const browserTimezone = () => {
  try { return Intl.DateTimeFormat().resolvedOptions().timeZone || '' } catch { return '' }
}

export default function Settings() {
  const [form, setForm] = useState({ business_name: '', timezone: '' })
  const [error, setError] = useState('')
  const [saved, setSaved] = useState(false)

  useEffect(() => {
    api('/api/auth/me').then((u) => {
      setForm({ business_name: u.business_name, timezone: u.timezone || '' })
    }).catch((e) => setError(e.message))
  }, [])

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setSaved(false)
    try {
      const updated = await api('/api/auth/me', {
        method: 'PATCH',
        body: { business_name: form.business_name, timezone: form.timezone || null },
      })
      auth.updateUser(updated)
      setSaved(true)
    } catch (err) { setError(err.message) }
  }

  return (
    <>
      <div className="page-head">
        <div>
          <h1>Settings</h1>
          <div className="sub">Business profile and timezone</div>
        </div>
      </div>

      <div className="card" style={{ maxWidth: 480 }}>
        <form onSubmit={submit}>
          <label>Business name
            <input required value={form.business_name}
              onChange={(e) => setForm({ ...form, business_name: e.target.value })} />
          </label>
          <label style={{ marginTop: 12, display: 'block' }}>Timezone
            <input value={form.timezone} placeholder="e.g. America/Chicago"
              onChange={(e) => setForm({ ...form, timezone: e.target.value })} />
          </label>
          <div className="muted" style={{ marginTop: 6 }}>
            Used for "this month" boundaries on the dashboard and forecast — otherwise the server's
            clock (UTC) is used.
            {form.timezone !== browserTimezone() && browserTimezone() && (
              <>
                {' '}Your browser reports <strong>{browserTimezone()}</strong>.{' '}
                <a href="#" onClick={(e) => { e.preventDefault(); setForm({ ...form, timezone: browserTimezone() }) }}>
                  Use it
                </a>.
              </>
            )}
          </div>
          {error && <div className="error" style={{ marginTop: 12 }}>{error}</div>}
          {saved && !error && <div className="up" style={{ marginTop: 12 }}>Saved.</div>}
          <button className="btn" style={{ marginTop: 14 }}>Save settings</button>
        </form>
      </div>
    </>
  )
}
