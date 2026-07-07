const TOKEN_KEY = 'keel_token'
const USER_KEY = 'keel_user'

// Decode a JWT's `exp` (seconds since epoch) without a library or signature
// verification — this only informs the UI whether to bother calling the API;
// the server is always the real authority on whether a token is valid.
function tokenExpiryMs(token) {
  try {
    const payload = JSON.parse(atob(token.split('.')[1].replace(/-/g, '+').replace(/_/g, '/')))
    return typeof payload.exp === 'number' ? payload.exp * 1000 : null
  } catch {
    return null
  }
}

export const auth = {
  token: () => localStorage.getItem(TOKEN_KEY),
  user: () => JSON.parse(localStorage.getItem(USER_KEY) || 'null'),
  // True only for a present, structurally-decodable, unexpired token.
  isValid() {
    const token = localStorage.getItem(TOKEN_KEY)
    if (!token) return false
    const expMs = tokenExpiryMs(token)
    return expMs == null || expMs > Date.now()
  },
  set(token, user) {
    localStorage.setItem(TOKEN_KEY, token)
    localStorage.setItem(USER_KEY, JSON.stringify(user))
  },
  // Merge a partial user update (e.g. after PATCH /api/auth/me) into the
  // cached copy, so the sidebar etc. reflect it without a full re-login.
  updateUser(patch) {
    const merged = { ...auth.user(), ...patch }
    localStorage.setItem(USER_KEY, JSON.stringify(merged))
    return merged
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
    // Navigation is already underway — never settle so callers don't render
    // an error flash for the instant before the browser leaves this page.
    return new Promise(() => {})
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
