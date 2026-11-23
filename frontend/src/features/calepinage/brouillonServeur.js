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
import { construireCle, hacherLayout } from './brouillon.js'

const AUCUN_DOCUMENT = 'aucun-document'

/* H1 (tour 3) — l'état de VUE que l'outil sérialise avec le document : `scene` = l'instant du soleil affiché (jour +
   heure ; saison, curseur d'heure, « Lire la journée » le changent — CALX119, « un point de vue, pas une donnée »).
   Regarder le soleil n'est pas une modification : ni « Modifications non enregistrées », ni brouillon (mesuré le
   22/11 : Été/Hiver sur le calepinage 9 envoyait 2 `PUT …/brouillon/` et écrasait celui d'un autre poste). Seule
   clé de vue du document : Plan/3D, zoom, déplacement, cadrage, couleurs d'ensoleillement ne sont pas sérialisés
   (même mesure). Un ENREGISTREMENT réel garde la sérialisation entière de l'outil : ceci ne sert qu'à comparer. */
export const CLES_VUE_DOCUMENT = Object.freeze(['scene'])

/** Le document SANS son état de vue (comparaison « modifié ? » et brouillon) ; tout autre valeur rendue telle quelle. */
export function sansVue(layout) {
  if (!layout || typeof layout !== 'object' || Array.isArray(layout)) return layout
  if (!CLES_VUE_DOCUMENT.some((cle) => cle in layout)) return layout
  const copie = { ...layout }
  for (const cle of CLES_VUE_DOCUMENT) delete copie[cle]
  return copie
}

/* ACAL1345 — choisir un pan dans la liste change `activeAreaId`, `outline` (contour du pan actif) et `pin` (centre du
   pan actif) dans le document, sans rien modifier de la conception : ces trois clés se DÉDUISENT des pans et du pan
   choisi. La COMPARAISON (« modifié ? », brouillon) les ignore ; le CONTENU du brouillon les garde (reprise intacte).
   `pin` ne s'ignore que s'il n'a pas été posé à la main (`pinSource: 'manuel'`) : une épingle déplacée EST une donnée. */
export const CLES_DERIVEES_DU_PAN_ACTIF = Object.freeze(['activeAreaId', 'outline'])

/** L'empreinte de comparaison d'un document : sans l'état de vue (`sansVue`) ni ce que le pan actif seul détermine. */
export function empreinteSansVue(layout) {
  const vue = sansVue(layout)
  if (!vue || typeof vue !== 'object' || Array.isArray(vue)) return hacherLayout(vue)
  const copie = { ...vue }
  for (const cle of CLES_DERIVEES_DU_PAN_ACTIF) delete copie[cle]
  if (copie.pinSource !== 'manuel') delete copie.pin
  return hacherLayout(copie)
}

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
  // ACAL1248 — compte les effacements par clé : un PUT encore EN ATTENTE dans la file quand sa clé est effacée
  // (enregistrement réussi) ne part plus — il serait suivi du DELETE, mais le serveur l'aurait gardé entre les deux.
  const effacements = new Map()
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
      const genEffacement = effacements.get(cle) ?? 0
      silencieux(() => (effacements.get(cle) ?? 0) === genEffacement
        ? envoyer(calepinageId, { layout, horodatage, base_empreinte: baseServeur(hashBase) }) : null)
    },
    removeItem(cle) {
      local.removeItem(cle)
      if (estBrouillon(cle)) effacements.set(cle, (effacements.get(cle) ?? 0) + 1)
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
