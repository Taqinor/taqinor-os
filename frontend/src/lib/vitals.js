/* VX61 — Web Vitals RÉELS terrain (INP/LCP/CLS/TTFB) → reporting maison.
 *
 * YHARD7 mesure le BUILD (bundle/Lighthouse) ; rien ne mesurait le TERRAIN.
 * Hand-rolled (`PerformanceObserver` natif) plutôt que la lib `web-vitals`
 * de Google (~2KB, nouvelle dépendance GATÉE — ce lane n'a pas accès à
 * `npm install`) : elle reste l'option préférée si le fondateur l'installe
 * plus tard, mais ce module fonctionne dès aujourd'hui sans elle, en
 * respectant les mêmes seuils good/needs-improvement/poor.
 *
 * No-op total si `window`/`PerformanceObserver` sont absents (SSR, tests,
 * navigateurs anciens) — jamais de throw, jamais d'impact sur le rendu.
 *
 * Backend : POST /api/django/reporting/vitals/ (apps/reporting/vitals.py) —
 * une ligne par métrique, company-scopée serveur ; agrégat p75 en GET
 * .../vitals/p75/. Table enregistrée au registre de rétention YOPSB10
 * (apps/reporting/services.py purge_web_vitals).
 */

const ENDPOINT = '/api/django/reporting/vitals/'

// Seuils Google (ms sauf CLS, sans unité) — good / needs-improvement / poor.
const THRESHOLDS = {
  LCP: [2500, 4000],
  INP: [200, 500],
  CLS: [0.1, 0.25],
  TTFB: [800, 1800],
}

/** Classement good/needs-improvement/poor pour une métrique+valeur. */
export function rateMetric(metric, value) {
  const t = THRESHOLDS[metric]
  if (!t || value == null || Number.isNaN(value)) return ''
  if (value <= t[0]) return 'good'
  if (value <= t[1]) return 'needs-improvement'
  return 'poor'
}

function randomId() {
  try {
    if (globalThis.crypto?.randomUUID) return globalThis.crypto.randomUUID()
  } catch {
    // repli ci-dessous
  }
  return `${Date.now()}-${Math.random().toString(36).slice(2, 10)}`
}

/** Forme exacte du corps envoyé au backend (exporté pour les tests). */
export function buildPayload(metric, value, route, navigationId) {
  return {
    route: route || '',
    metric,
    value: Math.round(value * 1000) / 1000,
    rating: rateMetric(metric, value),
    navigation_id: navigationId,
  }
}

/** Beacon best-effort — ne lève jamais, jamais bloquant pour l'app. */
function report(metric, value, route, navigationId) {
  try {
    const payload = JSON.stringify(buildPayload(metric, value, route, navigationId))
    const nav = globalThis.navigator
    if (nav?.sendBeacon) {
      const blob = new Blob([payload], { type: 'application/json' })
      if (nav.sendBeacon(ENDPOINT, blob)) return
    }
    globalThis.fetch?.(ENDPOINT, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: payload,
      keepalive: true,
    })?.catch(() => {})
  } catch {
    // Le monitoring de perf ne doit jamais faire planter l'app.
  }
}

let _initialised = false

/**
 * Démarre la capture terrain (LCP/CLS/INP-approximatif/TTFB). No-op si déjà
 * initialisé ou si les APIs requises sont absentes. `deps` est un point
 * d'injection réservé aux TESTS (jamais utilisé en prod) pour fournir un
 * `PerformanceObserver`/`window`/`document`/`report` mockés.
 */
export function initVitals(deps = {}) {
  if (_initialised) return false
  const win = deps.window || (typeof window !== 'undefined' ? window : undefined)
  const PO = deps.PerformanceObserver
    || (typeof PerformanceObserver !== 'undefined' ? PerformanceObserver : undefined)
  if (!win || typeof PO === 'undefined') return false
  _initialised = true

  const doc = deps.document || win.document
  const send = deps.report || report
  const route = () => win.location?.pathname || ''
  const navId = randomId()

  // ── LCP — dernière entrée avant que l'onglet passe en arrière-plan ──────
  let lastLcp = null
  try {
    const lcpObserver = new PO((list) => {
      const entries = list.getEntries()
      if (entries.length) lastLcp = entries[entries.length - 1].startTime
    })
    lcpObserver.observe({ type: 'largest-contentful-paint', buffered: true })
  } catch {
    // Type non supporté (Safari) — LCP simplement jamais rapporté.
  }

  // ── CLS — somme des décalages SANS interaction utilisateur récente ──────
  let clsValue = 0
  try {
    const clsObserver = new PO((list) => {
      for (const entry of list.getEntries()) {
        if (!entry.hadRecentInput) clsValue += entry.value
      }
    })
    clsObserver.observe({ type: 'layout-shift', buffered: true })
  } catch {
    // Type non supporté.
  }

  // ── INP (approximatif) — pire durée d'interaction observée ──────────────
  // Simplification assumée : la vraie métrique INP retient le 98e centile
  // (ou le pire sous 50 interactions) par groupe d'interaction ; ici on
  // retient simplement la pire durée `event` observée — un proxy honnête,
  // pas la valeur Google exacte.
  let worstInp = null
  try {
    const inpObserver = new PO((list) => {
      for (const entry of list.getEntries()) {
        if (worstInp == null || entry.duration > worstInp) worstInp = entry.duration
      }
    })
    inpObserver.observe({ type: 'event', durationThreshold: 40, buffered: true })
  } catch {
    // Type non supporté (Safari ne l'implémente pas encore).
  }

  // ── TTFB — Navigation Timing, disponible immédiatement ──────────────────
  try {
    const [navEntry] = win.performance?.getEntriesByType?.('navigation') || []
    if (navEntry && typeof navEntry.responseStart === 'number' && navEntry.responseStart > 0) {
      send('TTFB', navEntry.responseStart, route(), navId)
    }
  } catch {
    // API absente.
  }

  let flushed = false
  const flush = () => {
    if (flushed) return
    flushed = true
    if (lastLcp != null) send('LCP', lastLcp, route(), navId)
    send('CLS', clsValue, route(), navId)
    if (worstInp != null) send('INP', worstInp, route(), navId)
  }

  // `visibilitychange` (onglet caché) est le signal recommandé par Google
  // pour figer LCP/CLS ; `pagehide` couvre la fermeture directe (iOS Safari
  // ne fiabilise pas `unload`).
  doc?.addEventListener?.('visibilitychange', () => {
    if (doc.visibilityState === 'hidden') flush()
  })
  win.addEventListener?.('pagehide', flush)

  return true
}

/** Réservé aux tests : réarme l'initialisation entre deux cas. */
export function _resetVitalsForTests() {
  _initialised = false
}
