/* YJPB1 — JOURNAL DES PROBLÈMES VÉCUS PAR LES UTILISATEURS (côté navigateur).
 *
 * CE QUI MANQUAIT (incident Meryem du 02/11/2026 : « problème de connexion,
 * les prochaines étapes disparaissent, je dois me déconnecter/reconnecter »).
 * Quand une requête dépasse le délai de 20 s (`api/axios.js`), quand le
 * serveur répond 5xx, ou quand une erreur JavaScript non interceptée survient,
 * l'utilisateur voit un toast FR… et RIEN n'est gardé. L'enquête a dû se faire
 * sur le seul journal d'accès nginx (perdu au redéploiement, sans durées) :
 * aucune trace ne disait depuis QUEL écran, sur QUELLE route, pour QUI.
 * Sentry (VX72/QAH8, `lib/monitoring.js`) est câblé mais c'est un no-op total
 * tant qu'aucun `VITE_SENTRY_DSN` n'est configuré — c'est le cas en production.
 *
 * Ce module est la couche qui manque, et elle est VOLONTAIREMENT bête : un
 * POST best-effort vers `reporting.ProblemeClient`, qui fonctionne que Sentry
 * soit configuré ou non.
 *
 * TROIS RÈGLES ABSOLUES (un journal ne doit JAMAIS aggraver l'incident) :
 *   1. jamais bloquant, jamais de `throw` — tout est avalé ;
 *   2. jamais récursif : le transport est `fetch` (PAS l'instance axios, dont
 *      l'intercepteur appelle justement ce module) et un échec du POST n'est
 *      jamais lui-même signalé ;
 *   3. jamais un flot : dédoublonnage par signature sur une fenêtre d'une
 *      minute + plafond par tranche de 10 minutes (un écran qui boucle en erreur
 *      peut produire des dizaines d'erreurs par seconde).
 *
 * SANS DONNÉE PERSONNELLE : la route est normalisée (identifiants → `<id>`,
 * chaîne de requête retirée — elle peut porter un nom ou un e-mail de
 * recherche), le message est tronqué, aucun corps de réponse n'est envoyé.
 * `company`/`utilisateur`/famille de navigateur sont posés CÔTÉ SERVEUR.
 */
import { originFrom } from '../api/origin.js'
import { refreshSession } from '../api/refreshCoordinator.js'

// LECTEUR DE SESSION : INJECTÉ par l'appelant (`deps.sessionEstActive`), jamais
// importé ici. `providers/session-bridge` ouvre un `BroadcastChannel` au
// chargement du module (VX162) ; l'importer depuis ce journal garderait le
// processus `node --test` en vie indéfiniment (vérifié) — un module de journal
// doit rester PUR. Sans lecteur on considère « pas de session » et on n'envoie
// RIEN : un POST hors session ne produirait qu'un 401 de plus. Les deux
// appelants réels (`api/axios.js`, `lib/globalErrors.js`) l'injectent, et un
// test de garde le vérifie sur LEUR source.
const HORS_SESSION = () => false

const CHEMIN = '/api/django/reporting/problemes-client/'

/** Genres reconnus par le serveur (`reporting.ProblemeClient.Genre`). */
export const GENRES = {
  RESEAU: 'reseau',
  SERVEUR: 'serveur',
  SCRIPT: 'script',
  ECRAN: 'ecran',
}

// Un même problème qui se répète dans la minute ne vaut qu'UNE ligne : on veut
// savoir QUOI casse, pas compter les re-renders.
const FENETRE_DOUBLON_MS = 60000
// Plafond dur par TRANCHE de 10 minutes : même si tout part en vrille, le journal
// ne devient jamais lui-même la charge. ERR-JPB-PLAFOND-PAR-ONGLET — pas « par
// chargement de page » : l'onglet d'un commercial reste ouvert toute la journée,
// et un déploiement (22 routes en 502) le laissait muet jusqu'au rechargement.
const PLAFOND_PAR_TRANCHE = 40
const DUREE_TRANCHE_MS = 600000

let _debutTranche = null
let _envoyes = 0
const _vus = new Map()

/** Nouvelle tranche : compteur remis à zéro, signatures expirées oubliées. */
function ouvrirTrancheSiEchue(maintenant) {
  if (_debutTranche != null && maintenant - _debutTranche < DUREE_TRANCHE_MS) return
  _debutTranche = maintenant
  _envoyes = 0
  for (const [cle, vu] of _vus) {
    if (maintenant - vu >= FENETRE_DOUBLON_MS) _vus.delete(cle)
  }
}

/** Réservé aux tests : réarme le dédoublonnage et le plafond. */
export function _resetJournalPourTests() {
  _debutTranche = null
  _envoyes = 0
  _vus.clear()
}

/** Réservé aux tests : taille de la mémoire de dédoublonnage. */
export function _nombreSignaturesPourTests() {
  return _vus.size
}

// ERR-JPB-ECRAN-JAMAIS-EMIS — un chunk introuvable (404 après un déploiement,
// l'onglet garde l'ancien index) n'a pas de nom stable selon le navigateur : on
// le reconnaît au message pour lui donner UN code. `#306` / « Lazy element » :
// après le `preventDefault` de `vite:preloadError`, `lazy()` résout `undefined`
// et React tombe dans la boundary juste avant que le rechargement parte.
const MOTIFS_CHUNK = /dynamically imported module|Importing a module script failed|Unable to preload CSS|Lazy element type must resolve|Minified React error #306\b/i

function estErreurChunk(error) {
  return error?.name === 'ChunkLoadError' || MOTIFS_CHUNK.test(String(error?.message || ''))
}

/** Segment d'URL qui porte un identifiant plutôt qu'un nom de ressource. */
function estIdentifiant(segment) {
  if (/^\d+$/.test(segment)) return true
  // UUID, et plus généralement tout jeton long (jetons de partage public,
  // hachages) : jamais un nom de route. ERR-JPB-ROUTE-SLUG-MASQUE — sauf un
  // slug kebab-case (`bons-commande-fournisseur`) : il FAIT la route, le masquer
  // fusionne des routes différentes dans la signature et le résumé.
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)) return true
  if (/^[a-z]+(?:-[a-z]+)+$/.test(segment)) return false
  return segment.length >= 20 && /^[A-Za-z0-9._~-]+$/.test(segment)
}

/**
 * Chemin NORMALISÉ d'une URL : sans origine, sans chaîne de requête (elle peut
 * porter une recherche nommée), identifiants remplacés par `<id>` pour que
 * 500 appels sur 500 devis se regroupent en UNE ligne de journal.
 */
export function normaliserRoute(url) {
  let chemin = String(url || '')
  if (/^[a-z]+:\/\//i.test(chemin)) {
    try {
      chemin = new URL(chemin).pathname
    } catch {
      // URL illisible : on garde la chaîne telle quelle, tronquée plus bas.
    }
  }
  chemin = chemin.split('?')[0].split('#')[0]
  return chemin
    .split('/')
    .map((s) => (estIdentifiant(s) ? '<id>' : s))
    .join('/')
    .slice(0, 255)
}

/** Corps exact envoyé au serveur (exporté pour les tests). */
export function construireCorps({ genre, methode, route, statut, code, message, requestId, routeBrute }) {
  return {
    genre,
    methode: String(methode || '').slice(0, 8).toUpperCase(),
    // ADCG54 — une violation CSP porte l'ORIGINE bloquée (déjà réduite par l'adaptateur).
    route: routeBrute ? String(route || '').slice(0, 255) : normaliserRoute(route),
    ecran: normaliserRoute(globalThis.location?.pathname || ''),
    statut_reponse: typeof statut === 'number' && Number.isFinite(statut) ? statut : null,
    code: String(code || '').slice(0, 64),
    message: String(message || '').slice(0, 255),
    request_id: requestId || null,
  }
}

/** Signature de dédoublonnage : le problème, pas son horodatage. */
function signature(corps) {
  return [corps.genre, corps.methode, corps.route, corps.statut_reponse, corps.code].join('|')
}

/**
 * Signale UN problème vécu. Best-effort absolu : ne lève jamais et n'attend
 * pas la réponse. Renvoie `true` seulement si un envoi a réellement été
 * déclenché (dédoublonnage, plafond et absence de session renvoient `false`).
 *
 * `deps` est un point d'injection réservé aux TESTS (jamais utilisé en prod).
 */
export function signalerProbleme(probleme, deps = {}) {
  try {
    const connecte = deps.sessionEstActive || HORS_SESSION
    // L'endpoint est authentifié et company-scopé : hors session (page
    // publique, écran de login) on n'envoie RIEN — sinon chaque problème
    // produirait un 401 de plus, donc du bruit au lieu d'une trace (même
    // leçon que CAD177 sur le beacon Web Vitals).
    if (!connecte()) return false
    const maintenant = (deps.maintenant || Date.now)()
    ouvrirTrancheSiEchue(maintenant)
    if (_envoyes >= PLAFOND_PAR_TRANCHE) return false

    const corps = construireCorps(probleme)
    if (!corps.genre) return false

    const cle = signature(corps)
    const vu = _vus.get(cle)
    if (vu != null && maintenant - vu < FENETRE_DOUBLON_MS) return false
    _vus.set(cle, maintenant)
    _envoyes += 1

    const envoyer = deps.fetch || globalThis.fetch
    if (!envoyer) return false
    const base = originFrom(import.meta.env?.VITE_API_URL)
    const poster = () => envoyer(base + CHEMIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps),
      credentials: 'include',
      keepalive: true,
    })
    const rafraichir = deps.rafraichir || refreshSession
    poster()?.then?.((reponse) => {
      // ERR-JPB-BALISE-401-APRES-30-MIN — `sessionEstActive` est un drapeau
      // Redux : il ignore l'expiration du cookie (30 min). Sans ceci, une
      // erreur survenue avant toute requête axios perdait sa ligne en silence.
      // UN refresh et UN second envoi, dont la réponse n'est plus regardée.
      if (reponse?.status !== 401) return undefined
      return rafraichir(base).then(poster)
    })?.catch?.(() => {
      // RÈGLE 2 : un échec du journal n'est JAMAIS signalé (ce serait la
      // boucle parfaite — le réseau est coupé, donc le signalement du problème
      // réseau échoue, donc on signalerait cet échec…).
    })
    return true
  } catch {
    // RÈGLE 1 : le journal ne fait jamais planter l'application.
    return false
  }
}

// ERR-JPB-REQUEST-ID-PERDU — l'identifiant que Django pose sur chaque réponse
// relie la ligne à sa trace serveur (journaux, Sentry). Un 502 de nginx n'en a
// pas : Django était absent, et c'est une information.
function requestIdDe(reponse) {
  const candidat = reponse?.headers?.['x-request-id'] || reponse?.data?.error?.request_id
  return /^[0-9a-f]{32}$/i.test(String(candidat || '')) ? candidat : null
}

/**
 * Adaptateur pour une erreur axios (appelé par l'intercepteur de réponse). Ne
 * signale QUE les deux cas qui comptent et qui, jusqu'ici, ne laissaient
 * aucune trace serveur :
 *   - AUCUNE réponse reçue (délai de 20 s dépassé, réseau coupé) → `reseau` ;
 *   - réponse 5xx → `serveur`.
 * Un 4xx est un refus compris (401/403/404/409 : l'application les gère) et
 * n'est pas un « problème vécu » ; une annulation volontaire non plus.
 */
export function signalerErreurRequete(error, deps = {}) {
  try {
    const config = error?.config || {}
    const url = config.url || ''
    // RÈGLE 2 : jamais le journal lui-même.
    if (String(url).includes('problemes-client')) return false
    const statut = error?.response?.status
    if (statut == null) {
      // Annulation volontaire (AbortController) : l'écran a changé, ce n'est
      // pas un problème vécu. Axios la marque ERR_CANCELED.
      if (error?.code === 'ERR_CANCELED') return false
      return signalerProbleme({
        genre: GENRES.RESEAU,
        methode: config.method,
        route: url,
        statut: null,
        code: error?.code || 'ERR_NETWORK',
        message: error?.message,
      }, deps)
    }
    // ERR-JPB-REFRESH-MUET-SESSION-EXPIREE — bridé, le refresh n'a rien dit de la
    // session : ce 429-là est un problème vécu (`api/refreshCoordinator.js`).
    if (statut >= 500 || (statut === 429 && String(url).includes('token/refresh'))) {
      return signalerProbleme({
        genre: GENRES.SERVEUR,
        methode: config.method,
        route: url,
        statut,
        code: error?.response?.data?.error?.code || error?.code || '',
        message: error?.message,
        requestId: requestIdDe(error?.response),
      }, deps)
    }
    return false
  } catch {
    return false
  }
}

/**
 * Adaptateur pour une erreur JavaScript non interceptée (`lib/globalErrors.js`)
 * ou un écran tombé (`genre: 'ecran'`). Une erreur axios qui remonte jusqu'ici
 * est IGNORÉE : elle a déjà été signalée par l'intercepteur, avec sa route.
 */
export function signalerErreurScript(error, genre = GENRES.SCRIPT, deps = {}) {
  try {
    if (error?.isAxiosError || error?.config?.url) return false
    return signalerProbleme({
      genre,
      route: '',
      statut: null,
      code: estErreurChunk(error) ? 'ChunkLoadError' : (error?.name || 'Error'),
      message: error?.message || String(error),
    }, deps)
  } catch {
    return false
  }
}

/**
 * ADCG54 — `securitypolicyviolation` (navigateur) : une ligne `script`, code
 * `csp:<directive>`, route = ORIGINE bloquée seule (jamais la requête), sans
 * toast ; dédoublonnée dans la minute par `signalerProbleme`. `cible` : tests.
 */
export function installerViolationsCsp(deps = {}) {
  const cible = 'cible' in deps ? deps.cible : globalThis.document
  cible?.addEventListener?.('securitypolicyviolation', (event) => {
    try {
      const directive = String(event?.effectiveDirective || event?.violatedDirective || '').split(' ')[0]
      const bloquee = String(event?.blockedURI || '')
      let origine = bloquee.split(/[?#]/)[0]
      try { origine = new URL(bloquee).origin } catch { /* inline, eval, data : mot-clé gardé */ }
      signalerProbleme({ genre: GENRES.SCRIPT, route: origine, routeBrute: true, statut: null,
        code: `csp:${directive}`, message: `CSP ${directive} bloque ${origine}` }, deps)
    } catch {
      // RÈGLE 1 : le journal ne fait jamais planter l'application.
    }
  })
}

// Un seul rechargement par fenêtre : si le chunk manque ENCORE juste après, le
// serveur n'a pas la version (déploiement cassé) et recharger bouclerait.
const CLE_RECHARGEMENT_CHUNK = 'erp:rechargement-chunk'
const FENETRE_RECHARGEMENT_MS = 60000

/** Note le rechargement ; `false` s'il vient d'avoir lieu ou si on ne peut pas
 *  le noter (mode privé) : sans mémoire, pas de garde contre la boucle. */
function reserverRechargement(stockage, maintenant) {
  try {
    const dernier = Number(stockage.getItem(CLE_RECHARGEMENT_CHUNK))
    if (dernier && maintenant - dernier < FENETRE_RECHARGEMENT_MS) return false
    stockage.setItem(CLE_RECHARGEMENT_CHUNK, String(maintenant))
    return true
  } catch {
    return false
  }
}

/**
 * ERR-JPB-ECRAN-JAMAIS-EMIS — `vite:preloadError` : un chunk `lazy` est
 * introuvable. Une ligne `ecran` `ChunkLoadError`, puis UN rechargement ; sinon
 * l'erreur suit son cours jusqu'à la boundary, qui affiche son écran.
 * `cible`/`stockage`/`recharger` sont des points d'injection pour les tests.
 */
export function installerRechargementChunk(deps = {}) {
  const cible = 'cible' in deps ? deps.cible : globalThis.window
  if (!cible?.addEventListener) return
  cible.addEventListener('vite:preloadError', (event) => {
    try {
      signalerErreurScript(event?.payload || new Error('Importing a module script failed'), GENRES.ECRAN, deps)
      const stockage = deps.stockage || globalThis.sessionStorage
      const maintenant = (deps.maintenant || Date.now)()
      if (!reserverRechargement(stockage, maintenant)) return
      event?.preventDefault?.()
      const recharger = deps.recharger || (() => globalThis.location?.reload())
      recharger()
    } catch {
      // RÈGLE 1 : le journal ne fait jamais planter l'application.
    }
  })
}
