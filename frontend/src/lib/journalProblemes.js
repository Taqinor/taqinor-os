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
 *      minute + plafond par chargement de page (un écran qui boucle en erreur
 *      peut produire des dizaines d'erreurs par seconde).
 *
 * SANS DONNÉE PERSONNELLE : la route est normalisée (identifiants → `<id>`,
 * chaîne de requête retirée — elle peut porter un nom ou un e-mail de
 * recherche), le message est tronqué, aucun corps de réponse n'est envoyé.
 * `company`/`utilisateur`/famille de navigateur sont posés CÔTÉ SERVEUR.
 */
import { originFrom } from '../api/origin.js'

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
// Plafond dur par chargement de page : même si tout part en vrille, le journal
// ne devient jamais lui-même la charge.
const PLAFOND_PAR_PAGE = 40

let _envoyes = 0
const _vus = new Map()

/** Réservé aux tests : réarme le dédoublonnage et le plafond. */
export function _resetJournalPourTests() {
  _envoyes = 0
  _vus.clear()
}

/** Segment d'URL qui porte un identifiant plutôt qu'un nom de ressource. */
function estIdentifiant(segment) {
  if (/^\d+$/.test(segment)) return true
  // UUID, et plus généralement tout jeton long (jetons de partage public,
  // hachages) : jamais un nom de route.
  if (/^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i.test(segment)) return true
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
export function construireCorps({ genre, methode, route, statut, code, message }) {
  return {
    genre,
    methode: String(methode || '').slice(0, 8).toUpperCase(),
    route: normaliserRoute(route),
    ecran: normaliserRoute(globalThis.location?.pathname || ''),
    statut_reponse: typeof statut === 'number' && Number.isFinite(statut) ? statut : null,
    code: String(code || '').slice(0, 64),
    message: String(message || '').slice(0, 255),
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
    if (_envoyes >= PLAFOND_PAR_PAGE) return false

    const corps = construireCorps(probleme)
    if (!corps.genre) return false

    const maintenant = (deps.maintenant || Date.now)()
    const cle = signature(corps)
    const vu = _vus.get(cle)
    if (vu != null && maintenant - vu < FENETRE_DOUBLON_MS) return false
    _vus.set(cle, maintenant)
    _envoyes += 1

    const envoyer = deps.fetch || globalThis.fetch
    if (!envoyer) return false
    const base = originFrom(import.meta.env?.VITE_API_URL)
    envoyer(base + CHEMIN, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(corps),
      credentials: 'include',
      keepalive: true,
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
    if (statut >= 500) {
      return signalerProbleme({
        genre: GENRES.SERVEUR,
        methode: config.method,
        route: url,
        statut,
        code: error?.response?.data?.error?.code || error?.code || '',
        message: error?.message,
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
      code: error?.name || 'Error',
      message: error?.message || String(error),
    }, deps)
  } catch {
    return false
  }
}
