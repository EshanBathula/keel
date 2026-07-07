import { beforeEach, describe, expect, it, vi } from 'vitest'
import { api, auth, fmtMoney, fmtMonth, roundToCents } from './api.js'

function makeJwt(payload) {
  const b64 = (obj) => btoa(JSON.stringify(obj)).replace(/\+/g, '-').replace(/\//g, '_')
  return `${b64({ alg: 'none' })}.${b64(payload)}.sig`
}

beforeEach(() => {
  localStorage.clear()
  vi.restoreAllMocks()
})

describe('fmtMoney', () => {
  it('formats a positive dollar amount as whole-dollar USD', () => {
    expect(fmtMoney(1234.5)).toBe('$1,235')
  })
  it('formats zero', () => {
    expect(fmtMoney(0)).toBe('$0')
  })
  it('formats negative amounts', () => {
    expect(fmtMoney(-42)).toBe('-$42')
  })
  it('renders an em dash for null/undefined', () => {
    expect(fmtMoney(null)).toBe('—')
    expect(fmtMoney(undefined)).toBe('—')
  })
})

describe('fmtMonth', () => {
  it('formats a YYYY-MM key as short month + 2-digit year', () => {
    expect(fmtMonth('2026-07')).toBe('Jul 26')
    expect(fmtMonth('2026-01')).toBe('Jan 26')
    expect(fmtMonth('2026-12')).toBe('Dec 26')
  })
})

describe('roundToCents', () => {
  it('collapses float noise to the nearest cent', () => {
    expect(roundToCents(19.999999999998)).toBe(20)
  })
  it('leaves already-clean cent values alone', () => {
    expect(roundToCents(19.99)).toBe(19.99)
  })
  it('rounds half up', () => {
    expect(roundToCents(19.995)).toBe(20)
  })
})

describe('auth.isValid', () => {
  it('is false with no token', () => {
    expect(auth.isValid()).toBe(false)
  })

  it('is true for a token whose exp is in the future', () => {
    const token = makeJwt({ sub: '1', exp: Math.floor(Date.now() / 1000) + 3600 })
    localStorage.setItem('keel_token', token)
    expect(auth.isValid()).toBe(true)
  })

  it('is false for a token whose exp is in the past', () => {
    const token = makeJwt({ sub: '1', exp: Math.floor(Date.now() / 1000) - 3600 })
    localStorage.setItem('keel_token', token)
    expect(auth.isValid()).toBe(false)
  })

  it('fails open (true) for a structurally malformed token', () => {
    // The server is the real authority on validity; a decode failure here
    // shouldn't itself lock a user out client-side.
    localStorage.setItem('keel_token', 'not-a-jwt')
    expect(auth.isValid()).toBe(true)
  })
})

describe('auth.updateUser', () => {
  it('merges a partial update into the cached user', () => {
    auth.set('tok', { id: 1, email: 'a@b.com', business_name: 'Old' })
    const merged = auth.updateUser({ business_name: 'New' })
    expect(merged).toEqual({ id: 1, email: 'a@b.com', business_name: 'New' })
    expect(auth.user()).toEqual(merged)
  })
})

describe('api()', () => {
  it('attaches the bearer token and parses a JSON response', async () => {
    localStorage.setItem('keel_token', 'my-token')
    global.fetch = vi.fn().mockResolvedValue({
      status: 200, ok: true, json: async () => ({ hello: 'world' }),
    })
    const result = await api('/api/thing')
    expect(result).toEqual({ hello: 'world' })
    const [, options] = global.fetch.mock.calls[0]
    expect(options.headers.Authorization).toBe('Bearer my-token')
  })

  it('sends a JSON body with Content-Type for POST', async () => {
    global.fetch = vi.fn().mockResolvedValue({ status: 201, ok: true, json: async () => ({}) })
    await api('/api/thing', { method: 'POST', body: { a: 1 } })
    const [, options] = global.fetch.mock.calls[0]
    expect(options.method).toBe('POST')
    expect(options.headers['Content-Type']).toBe('application/json')
    expect(options.body).toBe(JSON.stringify({ a: 1 }))
  })

  it('returns null for a 204 response', async () => {
    global.fetch = vi.fn().mockResolvedValue({ status: 204, ok: true })
    expect(await api('/api/thing', { method: 'DELETE' })).toBeNull()
  })

  it('throws the server-provided detail message on failure', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      status: 400, ok: false, json: async () => ({ detail: 'Bad input' }),
    })
    await expect(api('/api/thing')).rejects.toThrow('Bad input')
  })

  it('falls back to a generic message when the error body has no detail', async () => {
    global.fetch = vi.fn().mockResolvedValue({
      status: 500, ok: false, json: async () => { throw new Error('not json') },
    })
    await expect(api('/api/thing')).rejects.toThrow('Request failed')
  })

  it('on 401, clears auth and never settles (redirect is already underway)', async () => {
    auth.set('tok', { id: 1 })
    global.fetch = vi.fn().mockResolvedValue({ status: 401, ok: false })
    // Avoid jsdom's "not implemented: navigation" noise for this assignment.
    delete window.location
    window.location = { href: '' }

    let settled = false
    api('/api/thing').then(() => { settled = true }).catch(() => { settled = true })

    await new Promise((r) => setTimeout(r, 10))
    expect(settled).toBe(false)
    expect(auth.token()).toBeNull()
    expect(window.location.href).toBe('/login')
  })
})
