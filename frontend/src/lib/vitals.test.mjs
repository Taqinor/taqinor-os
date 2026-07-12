// VX61 — Tests purs (node --test, aucune dépendance) du hand-roll Web
// Vitals : classement good/needs-improvement/poor, forme du payload,
// no-op sans PerformanceObserver, capture LCP/CLS/INP/TTFB via un
// PerformanceObserver mocké injecté, flush unique au passage en arrière-plan.
import test from 'node:test'
import assert from 'node:assert/strict'

import {
  rateMetric, buildPayload, initVitals, _resetVitalsForTests,
} from './vitals.js'

test.beforeEach(() => {
  _resetVitalsForTests()
})

test('rateMetric() classe LCP selon les seuils Google (2500/4000 ms)', () => {
  assert.equal(rateMetric('LCP', 2000), 'good')
  assert.equal(rateMetric('LCP', 2500), 'good')
  assert.equal(rateMetric('LCP', 3000), 'needs-improvement')
  assert.equal(rateMetric('LCP', 5000), 'poor')
})

test('rateMetric() classe CLS selon les seuils Google (0.1/0.25, sans unité)', () => {
  assert.equal(rateMetric('CLS', 0.05), 'good')
  assert.equal(rateMetric('CLS', 0.2), 'needs-improvement')
  assert.equal(rateMetric('CLS', 0.4), 'poor')
})

test('rateMetric() renvoie une chaîne vide pour une métrique inconnue ou une valeur invalide', () => {
  assert.equal(rateMetric('BOGUS', 100), '')
  assert.equal(rateMetric('LCP', null), '')
  assert.equal(rateMetric('LCP', NaN), '')
})

test('buildPayload() renvoie la forme exacte attendue par le serializer backend', () => {
  const payload = buildPayload('LCP', 2100.5555, '/ventes/devis', 'nav-1')
  assert.deepEqual(payload, {
    route: '/ventes/devis',
    metric: 'LCP',
    value: 2100.556,
    rating: 'good',
    navigation_id: 'nav-1',
  })
})

test('buildPayload() route vide par défaut plutôt que undefined/null', () => {
  const payload = buildPayload('CLS', 0.01, undefined, 'nav-2')
  assert.equal(payload.route, '')
})

test('initVitals() est un no-op sans PerformanceObserver (pas de window/PO)', () => {
  const started = initVitals({ window: undefined, PerformanceObserver: undefined })
  assert.equal(started, false)
})

test('initVitals() est idempotent : un second appel ne redémarre rien', () => {
  const calls = []
  const deps = makeFakeEnv({ onReport: (...args) => calls.push(args) })
  assert.equal(initVitals(deps), true)
  assert.equal(initVitals(deps), false)
})

test('initVitals() envoie TTFB immédiatement depuis Navigation Timing', () => {
  const calls = []
  const deps = makeFakeEnv({ onReport: (...args) => calls.push(args), responseStart: 650 })
  initVitals(deps)
  const ttfb = calls.find(([metric]) => metric === 'TTFB')
  assert.ok(ttfb, 'TTFB doit être envoyé sans attendre la fin de navigation')
  assert.equal(ttfb[1], 650)
})

test('initVitals() flush LCP/CLS/INP une seule fois, au passage en arrière-plan', () => {
  const calls = []
  const deps = makeFakeEnv({ onReport: (...args) => calls.push(args) })
  initVitals(deps)

  // Simule les entrées natives poussées par le navigateur aux observateurs.
  deps._emitters.lcp([{ startTime: 1800 }])
  deps._emitters.cls([{ value: 0.03, hadRecentInput: false }, { value: 0.5, hadRecentInput: true }])
  deps._emitters.event([{ duration: 120 }, { duration: 310 }])

  deps._hide()
  deps._hide() // second passage en arrière-plan → ne doit pas dupliquer l'envoi

  const byMetric = Object.fromEntries(calls.map(([m, v]) => [m, v]))
  assert.equal(byMetric.LCP, 1800)
  // CLS n'accumule QUE les décalages sans interaction récente (0.03, pas 0.5).
  assert.equal(byMetric.CLS, 0.03)
  assert.equal(byMetric.INP, 310)
  assert.equal(calls.filter(([m]) => m === 'LCP').length, 1)
})

test('initVitals() flush aussi sur pagehide (fermeture directe iOS Safari)', () => {
  const calls = []
  const deps = makeFakeEnv({ onReport: (...args) => calls.push(args) })
  initVitals(deps)
  deps._emitters.lcp([{ startTime: 900 }])
  deps._pagehide()
  assert.ok(calls.some(([m, v]) => m === 'LCP' && v === 900))
})

// ── Environnement PerformanceObserver factice ────────────────────────────
function makeFakeEnv({ onReport, responseStart = 0 } = {}) {
  const listeners = { visibilitychange: [], pagehide: [] }
  const emitters = {}

  class FakePerformanceObserver {
    constructor(cb) {
      this._cb = cb
    }

    observe({ type }) {
      emitters[type === 'largest-contentful-paint' ? 'lcp'
        : type === 'layout-shift' ? 'cls' : 'event'] = (entries) => {
        this._cb({ getEntries: () => entries })
      }
    }
  }

  const doc = {
    visibilityState: 'visible',
    addEventListener: (evt, fn) => {
      if (evt === 'visibilitychange') listeners.visibilitychange.push(fn)
    },
  }

  const win = {
    location: { pathname: '/test' },
    performance: {
      getEntriesByType: (t) => (t === 'navigation' ? [{ responseStart }] : []),
    },
    document: doc,
    addEventListener: (evt, fn) => {
      if (evt === 'pagehide') listeners.pagehide.push(fn)
    },
  }

  return {
    window: win,
    document: doc,
    PerformanceObserver: FakePerformanceObserver,
    report: (metric, value) => onReport(metric, value),
    _emitters: emitters,
    _hide: () => {
      doc.visibilityState = 'hidden'
      listeners.visibilitychange.forEach((fn) => fn())
    },
    _pagehide: () => listeners.pagehide.forEach((fn) => fn()),
  }
}
