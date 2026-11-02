// VX206 — Socle local d'observabilité : les DEUX listeners globaux qui
// manquaient totalement (`unhandledrejection`, `error`) canalisés vers le
// MÊME chemin captureException-ou-no-op que VX72 (`lib/monitoring.js`,
// consommé par `ui/ErrorBoundary.jsx` et `RouteErrorBoundary.jsx`) + un toast
// générique FR. Avant : une promesse rejetée dans un handler d'événement, une
// chaîne `.then()`, ou le `sender()` de l'outbox échouait en silence TOTAL —
// invisible même après VX72, qui ne câblait QUE
// `RouteErrorBoundary→captureException`.
//
// Fonction PURE côté logique (aucun composant React) — `installGlobalErrors`
// se contente d'attacher deux listeners `window`, feature-detect implicite
// (no-op si `window` est absent, ex. SSR/tests node).
import { captureException } from './monitoring'
// YJPB1 — journal maison des problèmes vécus : la trace survit même sans
// DSN Sentry (le cas en production), ce qui rendait `captureException`
// ci-dessus totalement muet.
import { signalerErreurScript } from './journalProblemes'
import { sessionEstActive } from '../providers/session-bridge'
import { toastError } from './toast'

let _installed = false

async function report(error) {
  console.error('[globalErrors]', error)
  // YJPB1 — AVANT `captureException` : ce journal-ci est celui qui fonctionne
  // sans DSN Sentry, donc celui qui ne doit jamais dépendre de lui.
  signalerErreurScript(error, undefined, { sessionEstActive })
  try {
    await captureException(error)
  } catch {
    // no-op — jamais planter pour un échec de reporting distant
  }
  toastError('Une erreur inattendue est survenue.')
}

/** Installe les listeners globaux (idempotent — un seul appel actif). */
export function installGlobalErrors() {
  if (_installed || typeof window === 'undefined') return
  _installed = true

  window.addEventListener('unhandledrejection', (event) => {
    const reason = event?.reason
    report(reason instanceof Error ? reason : new Error(String(reason)))
  })

  window.addEventListener('error', (event) => {
    // Les erreurs de ressource (img/script en échec) déclenchent aussi
    // 'error' sans `event.error` associé — hors périmètre (déjà silencieuses
    // sans impact fonctionnel, ne pas les toaster).
    if (!event?.error) return
    report(event.error)
  })
}

export default installGlobalErrors
