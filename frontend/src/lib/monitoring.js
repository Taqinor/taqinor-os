/* VX72 — Monitoring d'erreurs frontend (Sentry), gardé par DSN — miroir de
 * `backend/django_core/core/monitoring.py`.
 *
 * Couche de FONDATION : n'initialise le monitoring que si `VITE_SENTRY_DSN`
 * est configuré. Sans lui (le cas par défaut), c'est un NO-OP TOTAL : le SDK
 * n'est même pas importé, aucune donnée n'est envoyée, aucune requête
 * sortante n'a lieu. L'import de `@sentry/react` est un DYNAMIC IMPORT
 * paresseux, tolérant à son absence : le paquet n'est PAS un dépendance
 * `package.json` de ce dépôt (comme `sentry-sdk` côté backend, absent de
 * requirements.txt) — tant qu'il n'est pas installé, `initMonitoring()`
 * échoue silencieusement au `catch` de l'import. Budget YHARD7 respecté :
 * aucun `import` statique de `@sentry/react` nulle part → zéro octet dans le
 * bundle tant que la fonctionnalité n'est pas activée.
 *
 * Activation (étape du fondateur, dépendance externe + tier gratuit
 * plafonné) :
 *   1. `npm install @sentry/react` (DEP) ;
 *   2. renseigner `VITE_SENTRY_DSN` (+ éventuellement `VITE_SENTRY_ENVIRONMENT`)
 *      dans `.env`, puis rebuild (variable Vite, résolue au build).
 */

let _initialised = false
let _sentry = null

/** DSN Sentry configuré (chaîne vide = monitoring désactivé). */
export function sentryDsn() {
  return (import.meta.env?.VITE_SENTRY_DSN || '').trim()
}

/** Vrai uniquement si un DSN est configuré. */
export function isMonitoringEnabled() {
  return !!sentryDsn()
}

/**
 * Initialise Sentry si (et seulement si) un DSN est configuré. No-op total
 * quand le DSN est absent ou quand `@sentry/react` n'est pas installé.
 * Idempotent. Renvoie une promesse résolue à `true` si l'init a réellement
 * eu lieu.
 */
export async function initMonitoring() {
  if (_initialised) return true
  const dsn = sentryDsn()
  if (!dsn) return false
  try {
    // Import dynamique — jamais résolu tant que le paquet n'est pas installé
    // ET qu'aucun DSN n'est configuré (l'un ou l'autre suffit à rester no-op).
    // Paquet optionnel absent de package.json : un specifier VARIABLE empêche
    // vite/vitest de le résoudre statiquement au build (sinon échec « cannot
    // resolve »). Chargé au runtime uniquement, une fois Reda l'a installé + DSN.
    const pkg = '@sentry/react'
    _sentry = await import(/* @vite-ignore */ pkg)
  } catch {
    // Paquet absent (pas encore installé par le fondateur) → no-op silencieux.
    return false
  }
  _sentry.init({
    dsn,
    environment: import.meta.env?.VITE_SENTRY_ENVIRONMENT || undefined,
    tracesSampleRate: 0,
    sendDefaultPii: false,
  })
  _initialised = true
  return true
}

/**
 * Signale une exception capturée par une error boundary. No-op total (renvoie
 * `null`) si le monitoring n'est pas actif — jamais d'appel réseau, jamais
 * d'exception levée par l'appel lui-même.
 * @returns {Promise<string|null>} l'identifiant d'évènement Sentry (« code
 *   erreur à transmettre » affiché par l'UI), ou `null` en no-op.
 */
export async function captureException(error, context) {
  if (!isMonitoringEnabled()) return null
  const ok = await initMonitoring()
  if (!ok || !_sentry) return null
  try {
    return _sentry.captureException(error, context ? { extra: context } : undefined) || null
  } catch {
    return null
  }
}
