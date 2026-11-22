/* ============================================================================
   ACAL400 — LE BROUILLON DE L'ATELIER, AUSSI CÔTÉ SERVEUR (par utilisateur).
   ----------------------------------------------------------------------------
   `brouillon.js` (CALX68/ACAL84) n'écrit que dans le `localStorage` d'UN
   navigateur : un poste fermé en pleine conception perdait tout pour le
   téléphone ou le portable. Ce fichier n'y change rien — il fournit un
   stockage « MIROIR » qui DÉLÈGUE au `localStorage` (toujours la première
   source, hors ligne compris) et ENVOIE en plus chaque brouillon au serveur
   (`PUT`/`DELETE calepinages/<pk>/brouillon/`, contrat
   `calepinage_brouillon.json`) — best-effort, jamais une erreur d'écran.

   Les appels d'API sont INJECTÉS (`envoyer`/`effacer`/`lire`, typiquement
   `calepinageApi.calepinages.*`) : la logique reste testable sous `node:test`
   (`brouillon.test.mjs`), sans axios.

   `base_empreinte` = le dernier segment de la clé du brouillon, c.-à-d.
   l'empreinte « document » SERVEUR sur laquelle l'atelier a ouvert ; le
   segment `aucun-document` (document encore vide) part comme `""`, l'empreinte
   serveur de « rien ».
   ========================================================================== */
import { construireCle } from './brouillon.js'

const AUCUN_DOCUMENT = 'aucun-document'

/** L'empreinte que le serveur compare (`""` pour un document encore vide). */
export function baseServeur(hashBase) {
  return !hashBase || hashBase === AUCUN_DOCUMENT ? '' : String(hashBase)
}

/* Envoi au mieux : un échec (levé tout de suite ou rejeté plus tard) ne
   touche jamais l'écriture locale, qui a déjà eu lieu. R2-04 — les envois d'UN
   miroir partent EN FILE : un `DELETE` (après un enregistrement) ne peut plus
   être doublé en route par un `PUT` plus gros parti avant lui, et laisser
   le serveur avec un brouillon que l'on venait d'effacer. File vide : l'appel
   part tout de suite, comme avant. */
function creerFileEnvoi() {
  let precedent = null
  return (appel) => {
    const lancer = () => {
      try { return Promise.resolve(appel()) } catch (err) { return Promise.reject(err) }
    }
    const fini = (precedent ? precedent.then(lancer) : lancer()).catch(() => {})
    precedent = fini
    fini.then(() => { if (precedent === fini) precedent = null })
  }
}

/* Une forme canonique (clés triées) : le jsonb du serveur ne garde pas l'ordre des clés du navigateur. */
function canonique(valeur) {
  if (Array.isArray(valeur)) return valeur.map(canonique)
  if (valeur && typeof valeur === 'object') {
    return Object.keys(valeur).sort().reduce((acc, cle) => { acc[cle] = canonique(valeur[cle]); return acc }, {})
  }
  return valeur
}
const memeDocument = (a, b) => JSON.stringify(canonique(a)) === JSON.stringify(canonique(b))

/** Le brouillon local `{layout, horodatage}`, ou `null` s'il est illisible. */
function lireBrouillonLocal(valeur) {
  try { return JSON.parse(valeur) } catch { return null }
}

/**
 * Le stockage MIROIR : même contrat Web Storage que `base` (les exceptions de
 * `base` remontent telles quelles — `brouillon.js` en a besoin pour sonder),
 * plus un envoi serveur pour les seules clés de brouillon de CE calepinage.
 */
export function creerStockageMiroir({ base, calepinageId, envoyer, effacer }) {
  if (!base) return null // sans localStorage, brouillon.js n'écrit rien (CALX68)
  const local = base
  const silencieux = creerFileEnvoi()
  const cleModele = construireCle({ calepinageId, utilisateurId: 'u', hashBase: 'h' })
  const prefixe = cleModele.slice(0, cleModele.indexOf(':', cleModele.indexOf(':') + 1) + 1)
  const estBrouillon = (cle) => typeof cle === 'string' && cle.startsWith(prefixe)
  return {
    getItem: (cle) => local.getItem(cle),
    setItem(cle, valeur) {
      local.setItem(cle, valeur)
      if (!estBrouillon(cle) || typeof envoyer !== 'function') return
      // Un brouillon illisible reste local : le serveur n'en reçoit rien.
      const brouillon = lireBrouillonLocal(valeur)
      if (!brouillon) return
      const { layout, horodatage } = brouillon
      const hashBase = cle.slice(cle.lastIndexOf(':') + 1)
      silencieux(() => envoyer(calepinageId, { layout, horodatage, base_empreinte: baseServeur(hashBase) }))
    },
    removeItem(cle) {
      local.removeItem(cle)
      if (estBrouillon(cle) && typeof effacer === 'function') {
        silencieux(() => effacer(calepinageId))
      }
    },
    get length() { return local.length },
    key: (i) => local.key?.(i) ?? null,
  }
}

/**
 * Le brouillon SERVEUR à proposer au bandeau de reprise, ou `null` : `{layout,
 * horodatage, serveur: true}` seulement s'il porte l'empreinte d'ouverture
 * (`hashBase`) — le serveur rend déjà `null` pour un brouillon périmé ; ce
 * contrôle couvre la course « document enregistré entre-temps ». R2-04 —
 * `layoutServi` (le document que le serveur sert) : un brouillon IDENTIQUE à lui
 * ne porte rien de non enregistré, il n'est jamais proposé.
 */
export async function lireBrouillonServeur({ lire, calepinageId, hashBase, layoutServi = null }) {
  if (typeof lire !== 'function' || calepinageId == null) return null
  try {
    const res = await lire(calepinageId)
    const b = res?.data
    if (!b || typeof b !== 'object' || b.layout == null) return null
    if ((b.base_empreinte ?? '') !== baseServeur(hashBase)) return null
    if (layoutServi && memeDocument(b.layout, layoutServi)) return null
    return { layout: b.layout, horodatage: b.horodatage, serveur: true }
  } catch {
    return null
  }
}
