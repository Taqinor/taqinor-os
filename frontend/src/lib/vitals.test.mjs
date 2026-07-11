// VX61 — Tests purs (node --test) du hand-roll Web Vitals : jamais de
// plantage sans PerformanceObserver, idempotent, beacon envoyé via
// sendBeacon (repli fetch keepalive) sans dépendance réseau réelle.
import { test } from 'node:test'
import assert from 'node:assert/strict'

function setGlobal(name, value) {
  Object.defineProperty(globalThis, name, {
    value, configurable: true, writable: true,
  })
}

test('initVitals() ne plante jamais sans PerformanceObserver (SSR/vieux navigateur)', async () => {
  setGlobal('PerformanceObserver', undefined)
  setGlobal('window', {})
  const mod = await import(`./vitals.js?nocase=${Math.random()}`)
  assert.doesNotThrow(() => mod.initVitals())
})

test('initVitals() est idempotent (observe une seule fois même appelé plusieurs fois)', async () => {
  let observeCalls = 0
  class FakePO {
    constructor(cb) { this.cb = cb }
    observe() { observeCalls += 1 }
  }
  setGlobal('PerformanceObserver', FakePO)
  setGlobal('window', {})
  setGlobal('navigator', { sendBeacon: () => true })
  setGlobal('location', { pathname: '/test' })
  setGlobal('performance', { getEntriesByType: () => [] })
  setGlobal('document', { visibilityState: 'visible' })
  setGlobal('addEventListener', () => {})

  const mod = await import(`./vitals.js?nocase=${Math.random()}`)
  mod.initVitals()
  const firstCount = observeCalls
  mod.initVitals()
  assert.equal(observeCalls, firstCount, 'un second appel ne doit rien ré-observer')
})

test('initVitals() capte TTFB depuis performance.getEntriesByType et envoie via sendBeacon', async () => {
  const sent = []
  class FakePO {
    constructor() {}
    observe() {}
  }
  setGlobal('PerformanceObserver', FakePO)
  setGlobal('window', {})
  setGlobal('navigator', {
    sendBeacon: (url, blob) => { sent.push({ url, blob }); return true },
  })
  setGlobal('location', { pathname: '/vitals-test' })
  setGlobal('performance', {
    getEntriesByType: (type) => (type === 'navigation' ? [{ responseStart: 123.4 }] : []),
  })
  setGlobal('document', { visibilityState: 'visible' })
  setGlobal('addEventListener', () => {})
  setGlobal('Blob', class { constructor(parts) { this.parts = parts } })

  const mod = await import(`./vitals.js?nocase=${Math.random()}`)
  mod.initVitals()

  assert.equal(sent.length, 1)
  assert.match(sent[0].url, /\/api\/django\/reporting\/vitals\/$/)
  const body = JSON.parse(sent[0].blob.parts[0])
  assert.equal(body.name, 'TTFB')
  assert.equal(body.value, 123.4)
  assert.equal(body.path, '/vitals-test')
})

test('sendMetric() ne plante jamais si sendBeacon et fetch sont tous deux absents', async () => {
  class FakePO {
    constructor() {}
    observe() { throw new Error('layout-shift non supporté') }
  }
  setGlobal('PerformanceObserver', FakePO)
  setGlobal('window', {})
  setGlobal('navigator', {})
  setGlobal('location', { pathname: '/x' })
  setGlobal('performance', { getEntriesByType: () => [] })
  setGlobal('document', { visibilityState: 'visible' })
  setGlobal('addEventListener', () => {})
  setGlobal('fetch', undefined)

  const mod = await import(`./vitals.js?nocase=${Math.random()}`)
  assert.doesNotThrow(() => mod.initVitals())
})
