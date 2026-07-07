import '@testing-library/jest-dom/vitest'

// Node 22+'s experimental global `localStorage` getter isn't in vitest's
// jsdom window-key whitelist, so jsdom's real localStorage never gets
// installed over it — `localStorage` ends up permanently undefined. A tiny
// in-memory polyfill sidesteps that conflict entirely.
class MemoryStorage {
  #store = new Map()
  getItem(key) { return this.#store.has(key) ? this.#store.get(key) : null }
  setItem(key, value) { this.#store.set(key, String(value)) }
  removeItem(key) { this.#store.delete(key) }
  clear() { this.#store.clear() }
  key(i) { return Array.from(this.#store.keys())[i] ?? null }
  get length() { return this.#store.size }
}

Object.defineProperty(globalThis, 'localStorage', {
  value: new MemoryStorage(),
  configurable: true,
  writable: true,
})

// jsdom has no layout engine, so Recharts' ResponsiveContainer (which uses
// ResizeObserver to size the chart) needs a no-op stand-in to mount at all.
global.ResizeObserver = class {
  observe() {}
  unobserve() {}
  disconnect() {}
}
