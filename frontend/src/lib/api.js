const TOKEN_KEY = 'keel_token'
const USER_KEY = 'keel_user'

export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  user: () => JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  set(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  clear() {
    localStorage.removeItem(TOKEN_KEY)
    localStorage.removeItem(USER_KEY)
  },
}

export async function api(path, { method = 'GET', body, formData } = {}) {
  const headers = {}
  const token = auth.token()
  if (token) headers.Authorization = `Bearer ${token}`
  if (body) headers['Content-Type'] = 'application/json'
  const res = await fetch(path, {
    method,
    headers,
    body: formData || (body ? JSON.stringify(body) : undefined),
  })
  if (res.status === 401) {
    auth.clear()
    window.location.href = '/login'
    throw new Error('Session expired')
  }
  if (!res.ok) {
    let detail = 'Request failed'
    try { detail = (await res.json()).detail || detail } catch { /* noop */ }
    throw new Error(typeof detail === 'string' ? detail : 'Request failed')
  }
  if (res.status === 204) return null
  return res.json()
}

// Collapse float input noise (e.g. 19.999999999998) to the nearest cent before
// it reaches the API, which stores and computes in integer cents.
export const roundToCents = (n) => Math.round(n * 100) / 100

export const fmtMoney = (n) =>
  n == null ? '—' : n.toLocaleString('en-US', { style: 'currency', currency: 'USD', maximumFractionDigits: 0 })

export const fmtMonth = (ym) => {
  const [y, m] = ym.split('-').map(Number)
  return new Date(y, m - 1, 1).toLocaleString('en-US', { month: 'short', year: '2-digit' })
}
