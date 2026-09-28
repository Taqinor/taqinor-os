/* VX72/QAH8 — Monitoring d'erreurs frontend (Sentry), gardé par DSN — miroir
 * de `backend/django_core/core/monitoring.py`.
 *
 * Couche de FONDATION : n'initialise le monitoring que si `VITE_SENTRY_DSN`
 * est configuré. Sans lui (le cas par défaut), c'est un NO-OP TOTAL : le SDK
 * n'est même pas importé, aucune donnée n'est envoyée, aucune requête
 * sortante n'a lieu. L'import de `@sentry/react` est un DYNAMIC IMPORT
 * paresseux, tolérant à son absence : même DEVENU une dépendance
 * `package.json` (QAH8), le specifier reste une VARIABLE (jamais un `import`
 * statique) — budget YHARD7 respecté : zéro octet du SDK dans le bundle
 * principal tant que `initMonitoring()` n'est pas réellement appelé (première
 * erreur capturée), DSN ou pas.
 *
 * QAH8 — armement pilote :
 *   - `replayIntegration` (session replay) : masquage de TOUT texte/saisie
 *     par défaut (données clients dans l'ERP) + blocage des médias,
 *     échantillonnage bas (10 % des sessions, 100 % sur erreur) ;
 *   - tag `company` posé côté React comme côté Django (`bindCompany`, miroir
 *     de `core.monitoring.bind_company` — mémorisé puis appliqué dès que le
 *     SDK est chargé, jamais d'appel réseau supplémentaire pour le poser).
 *
 * Activation (étape du fondateur, dépendance externe + tier gratuit
 * plafonné) :
 *   1. `npm install @sentry/react` (déjà en dépendance depuis QAH8 — geste
 *      restant : renseigner le DSN) ;
 *   2. renseigner `VITE_SENTRY_DSN` (+ éventuellement `VITE_SENTRY_ENVIRONMENT`)
 *      dans `.env` (voir `.env.example`, `docker-compose.yml` pour le build
 *      arg), puis rebuild (variable Vite, résolue au build).
 */

let _initialised = false
let _sentry = null
// QAH8 — société à taguer, mémorisée avant même l'init (le SDK peut ne
// charger qu'au premier appel de `captureException`, bien après la connexion
// de l'utilisateur). `undefined` = jamais posée ; `null` = explicitement
// effacée (déconnexion).
let _pendingCompanyId

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
    // QAH8 — session replay : échantillonnage bas (le pilote n'a pas besoin
    // de tout voir) mais 100 % dès qu'une erreur survient (c'est justement le
    // cas qui compte). Masquage explicite même si ce sont déjà les défauts du
    // SDK : les écrans de l'ERP affichent des données clients (devis, leads,
    // factures), jamais un pari sur un défaut amont qui pourrait changer.
    replaysSessionSampleRate: 0.1,
    replaysOnErrorSampleRate: 1.0,
    integrations: [
      _sentry.replayIntegration({
        maskAllText: true,
        maskAllInputs: true,
        blockAllMedia: true,
      }),
    ],
  })
  _initialised = true
  // Applique le tag company mémorisé AVANT que le SDK soit chargé (cas normal
  // : l'utilisateur est connecté bien avant la première exception capturée).
  if (_pendingCompanyId !== undefined) _appliquerTagCompany(_pendingCompanyId)
  return true
}

/** Pose (ou efface, avec `null`) le tag Sentry `company` sur le SDK chargé. */
function _appliquerTagCompany(companyId) {
  try {
    _sentry.setTag('company', companyId == null ? null : String(companyId))
  } catch {
    // no-op — un tag ne doit jamais faire planter l'appelant.
  }
}

/**
 * QAH8 — associe la société courante aux futurs évènements Sentry, comme
 * `core.monitoring.bind_company` côté Django. À appeler là où la société de
 * l'utilisateur est déjà connue (ex. après `/auth/me/`) — jamais de résolution
 * réseau ajoutée ici. No-op inoffensif si le SDK n'est pas encore chargé (DSN
 * absent, ou pas encore de première erreur capturée) : la valeur est
 * mémorisée et posée dès que `initMonitoring()` réussit. Ne lève jamais.
 */
export function bindCompany(companyId) {
  _pendingCompanyId = companyId ?? null
  if (_sentry) _appliquerTagCompany(_pendingCompanyId)
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
