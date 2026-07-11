// VX61 — Web Vitals RÉELS (INP/LCP/CLS/TTFB) captés côté terrain, envoyés au
// reporting maison. YHARD7 mesure le BUILD (bundle/perf synthétique) ; rien ne
// mesurait le TERRAIN (réseau 3G rurale, devices bas de gamme des équipes
// terrain). Hand-roll `PerformanceObserver` (pas de dépendance `web-vitals` —
// GATED, non ajoutée ici pour rester à coût zéro par défaut) : défensif à
// 100%, silencieux si l'API est absente (vieux navigateurs / jsdom en test).
//
// Envoi via `navigator.sendBeacon` (fire-and-forget, survit à la fermeture
// d'onglet) avec repli `fetch(..., {keepalive: true})` si absent. Chaque
// métrique part en POST indépendant vers
// `/api/django/reporting/vitals/` (scoping société posé CÔTÉ SERVEUR).
import { originFrom } from '../api/origin.js'

const ENDPOINT_PATH = '/api/django/reporting/vitals/'

function endpointUrl() {
  const origin = originFrom(import.meta.env?.VITE_API_URL)
  return origin ? `${origin}${ENDPOINT_PATH}` : ENDPOINT_PATH
}

/** Envoie une métrique au backend. Ne lève jamais. */
function sendMetric(name, value, extra) {
  try {
    const payload = JSON.stringify({
      name,
      value,
      path: typeof location !== 'undefined' ? location.pathname : '',
      ...extra,
    })
    const url = endpointUrl()
    if (typeof navigator !== 'undefined' && navigator.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' })
      const ok = navigator.sendBeacon(url, blob)
      if (ok) return
    }
    if (typeof fetch === 'function') {
      fetch(url, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: payload,
        keepalive: true,
        credentials: 'include',
      }).catch(() => {
        // Best-effort : une métrique perdue n'est jamais bloquante.
      })
    }
  } catch {
    // Défensif : la mesure de perf ne doit jamais casser l'app.
  }
}

/** LCP — Largest Contentful Paint (dernière valeur observée avant unload). */
function observeLCP() {
  let last = null
  try {
    const po = new PerformanceObserver((list) => {
      const entries = list.getEntries()
      const entry = entries[entries.length - 1]
      if (entry) last = entry.startTime
    })
    po.observe({ type: 'largest-contentful-paint', buffered: true })
    const flush = () => {
      if (last != null) sendMetric('LCP', last)
    }
    addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flush()
    })
    addEventListener('pagehide', flush)
  } catch {
    // API absente (navigateur ancien / jsdom) — silencieux.
  }
}

/** CLS — Cumulative Layout Shift (somme des shifts sans input récent). */
function observeCLS() {
  let clsValue = 0
  try {
    const po = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) clsValue += entry.value
      }
    })
    po.observe({ type: 'layout-shift', buffered: true })
    const flush = () => sendMetric('CLS', clsValue)
    addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flush()
    })
    addEventListener('pagehide', flush)
  } catch {
    // Silencieux.
  }
}

/** INP — Interaction to Next Paint (pire interaction observée). */
function observeINP() {
  let worst = 0
  try {
    const po = new PerformanceObserver((list) => {
      for (const entry of list.getEntries()) {
        const duration = entry.duration || 0
        if (duration > worst) worst = duration
      }
    })
    po.observe({ type: 'event', buffered: true, durationThreshold: 40 })
    const flush = () => {
      if (worst > 0) sendMetric('INP', worst)
    }
    addEventListener('visibilitychange', () => {
      if (document.visibilityState === 'hidden') flush()
    })
    addEventListener('pagehide', flush)
  } catch {
    // Silencieux (Safari n'implémente pas 'event' bufferisé partout).
  }
}

/** TTFB — Time to First Byte, depuis l'entrée de navigation. */
function observeTTFB() {
  try {
    const [nav] = performance.getEntriesByType('navigation')
    if (nav && typeof nav.responseStart === 'number') {
      sendMetric('TTFB', nav.responseStart)
    }
  } catch {
    // Silencieux.
  }
}

let started = false

/** Démarre la capture des Web Vitals. Idempotent, sans effet en SSR/test. */
export function initVitals() {
  if (started) return
  if (typeof window === 'undefined' || typeof PerformanceObserver === 'undefined') {
    return
  }
  started = true
  observeTTFB()
  observeLCP()
  observeCLS()
  observeINP()
}

export default initVitals
