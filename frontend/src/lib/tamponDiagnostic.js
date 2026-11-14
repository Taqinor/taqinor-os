// COP6 — tampon de diagnostic du navigateur (contrat : `contexte.diagnostic` de
// `backend/django_core/apps/agent/contract_samples/assistant_reponse.json`).
//
// INTERFACE FIGÉE entre l'intercepteur réseau (qui note) et le panneau de
// l'assistant (qui lit `instantaneDiagnostic()` pour « Signaler un bug ») :
//
//   noterRequete({ methode, url, statut, dureeMs, requestId, code })
//   noterErreur({ genre, message })
//   instantaneDiagnostic()  -> { version, ecran, navigateur, en_ligne, requetes[], erreurs[] }
//   viderTampon()
//
// Jamais de donnée personnelle : ni corps de requête, ni chaîne de requête,
// routes normalisées (`<id>`), 15 requêtes et 10 erreurs au plus, en mémoire
// seulement (rien n'est écrit dans le navigateur).

export const MAX_REQUETES = 15
export const MAX_ERREURS = 10

const requetes = []
const erreurs = []

// Identifiant de build : le front n'en connaît aucun aujourd'hui (pas de
// variable de build dédiée, et on n'en crée pas) — chaîne vide.
const VERSION_BUILD = ''

const LONGUEUR_MAX_MESSAGE = 200
const LONGUEUR_MAX_CODE = 40
const RE_UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i

function maintenant() {
  return Date.now()
}

function segmentEstIdentifiant(seg) {
  if (!seg) return false
  if (/^\d+$/.test(seg)) return true
  if (RE_UUID.test(seg)) return true
  const alphabetJeton = /^[A-Za-z0-9_-]+$/.test(seg)
  // Jeton / identifiant long.
  if (seg.length >= 16 && alphabetJeton) return true
  // Segment mêlant lettres et chiffres (hash court, slug à numéro) : suspect.
  return seg.length >= 8 && alphabetJeton && /\d/.test(seg) && /[A-Za-z]/.test(seg)
}

/** Route normalisée : sans origine, sans chaîne de requête ni fragment, les
 *  segments identifiants remplacés par `<id>`. Jamais de donnée personnelle. */
export function normaliserRoute(url) {
  let chemin = String(url == null ? '' : url)
  chemin = chemin.replace(/^[a-z][a-z0-9+.-]*:\/\/[^/?#]*/i, '')
  chemin = chemin.split(/[?#]/)[0]
  return chemin.split('/').map((s) => (segmentEstIdentifiant(s) ? '<id>' : s)).join('/')
}

/** Message nettoyé : e-mails, téléphones et longues suites de chiffres
 *  retirés, puis tronqué. */
export function nettoyerMessage(message) {
  let m = String(message == null ? '' : message)
  m = m.replace(/[^\s@]+@[^\s@]+\.[^\s@]+/g, '<email>')
  m = m.replace(/\+?\d[\d\s.\-()]{6,}\d/g, '<nombre>')
  m = m.replace(/\d{5,}/g, '<nombre>')
  return m.slice(0, LONGUEUR_MAX_MESSAGE)
}

function pousser(anneau, ligne, max) {
  anneau.push(ligne)
  while (anneau.length > max) anneau.shift()
}

function codeCourt(code) {
  if (typeof code !== 'string') return ''
  const c = code.trim()
  return c && c.length <= LONGUEUR_MAX_CODE && /^[\w.:-]+$/.test(c) ? c : ''
}

export function noterRequete({ methode, url, statut, dureeMs, requestId, code } = {}) {
  try {
    pousser(requetes, {
      methode: String(methode || 'GET').toUpperCase().slice(0, 10),
      route: normaliserRoute(url),
      statut: Number.isFinite(Number(statut)) ? Number(statut) : 0,
      duree_ms: Number.isFinite(Number(dureeMs)) ? Math.max(0, Math.round(Number(dureeMs))) : 0,
      request_id: /^[0-9a-f]{32}$/i.test(String(requestId || '')) ? String(requestId) : '',
      code: codeCourt(code),
      _t: maintenant(),
    }, MAX_REQUETES)
  } catch {
    // Le tampon ne fait jamais planter l'application.
  }
}

export function noterErreur({ genre, message } = {}) {
  try {
    pousser(erreurs, {
      genre: String(genre || 'script').replace(/[^\w.-]/g, '').slice(0, 20) || 'script',
      message: nettoyerMessage(message),
      _t: maintenant(),
    }, MAX_ERREURS)
  } catch {
    // Le tampon ne fait jamais planter l'application.
  }
}

function familleNavigateur() {
  const ua = typeof navigator !== 'undefined' ? String(navigator.userAgent || '') : ''
  if (/Edg(e|A|iOS)?\//.test(ua)) return 'Edge'
  if (/Firefox\/|FxiOS\//.test(ua)) return 'Firefox'
  if (/Chrome\/|CriOS\//.test(ua)) return 'Chrome'
  if (/Safari\//.test(ua)) return 'Safari'
  return 'autre'
}

function ecranCourant() {
  try {
    return normaliserRoute(globalThis.location?.pathname || '')
  } catch {
    return ''
  }
}

function enLigne() {
  return typeof navigator !== 'undefined' && 'onLine' in navigator ? navigator.onLine !== false : true
}

export function instantaneDiagnostic() {
  const now = maintenant()
  const sansHorloge = ({ _t, ...reste }) => ({
    ...reste,
    il_y_a_s: Math.max(0, Math.round((now - _t) / 1000)),
  })
  return {
    version: VERSION_BUILD,
    ecran: ecranCourant(),
    navigateur: familleNavigateur(),
    en_ligne: enLigne(),
    requetes: requetes.map(sansHorloge).reverse(),
    erreurs: erreurs.map(sansHorloge).reverse(),
  }
}

export function viderTampon() {
  requetes.length = 0
  erreurs.length = 0
}

// Déconnexion (événement émis par `logoutUser`, LW45) : le relevé d'un compte ne
// suit jamais le compte suivant sur le même navigateur.
export const EVENEMENT_DECONNEXION = 'taqinor:auth-logout'
if (typeof globalThis.addEventListener === 'function') {
  globalThis.addEventListener(EVENEMENT_DECONNEXION, viderTampon)
}
