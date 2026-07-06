import { useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, auth } from '../lib/api.js'

export default function Login() {
  const navigate = useNavigate()
  const [mode, setMode] = useState('login')
  const [form, setForm] = useState({ email: '', password: '', business_name: '' })
  const [error, setError] = useState('')
  const [busy, setBusy] = useState(false)

  const submit = async (e) => {
    e.preventDefault()
    setError('')
    setBusy(true)
    try {
      const path = mode === 'login' ? '/api/auth/login' : '/api/auth/register'
      const body = mode === 'login'
        ? { email: form.email, password: form.password }
        : { email: form.email, password: form.password, business_name: form.business_name || 'My Business' }
      const data = await api(path, { method: 'POST', body })
      auth.set(data.access_token, data.user)
      navigate('/')
    } catch (err) {
      setError(err.message)
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="auth-wrap">
      <div className="auth-card">
        <h1>Keel</h1>
        <p className="tagline">Financial intelligence that keeps your business steady.</p>
        <form onSubmit={submit}>
          {mode === 'register' && (
            <label>
              Business name
              <input value={form.business_name} placeholder="Harbor Coffee Co."
                onChange={(e) => setForm({ ...form, business_name: e.target.value })} />
            </label>
          )}
          <label>
            Email
            <input type="email" required value={form.email}
              onChange={(e) => setForm({ ...form, email: e.target.value })} />
          </label>
          <label>
            Password
            <input type="password" required minLength={8} value={form.password}
              onChange={(e) => setForm({ ...form, password: e.target.value })} />
          </label>
          {error && <div className="error">{error}</div>}
          <button className="btn" disabled={busy}>
            {busy ? 'One moment…' : mode === 'login' ? 'Sign in' : 'Create account'}
          </button>
        </form>
        <p className="muted" style={{ marginTop: 14 }}>
          {mode === 'login' ? (
            <>New to Keel? <a href="#" onClick={(e) => { e.preventDefault(); setMode('register') }}>Create an account</a></>
          ) : (
            <>Already have an account? <a href="#" onClick={(e) => { e.preventDefault(); setMode('login') }}>Sign in</a></>
          )}
        </p>
        <p className="muted" style={{ marginTop: 6 }}>Demo: demo@keel.app / demopassword</p>
      </div>
    </div>
  )
}
