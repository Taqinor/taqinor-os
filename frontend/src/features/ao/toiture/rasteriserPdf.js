/* AOF79 — Rastérisation d'un plan source (PDF) en fond de calque : LOGIQUE PURE.
   ----------------------------------------------------------------------------
   Ce module ne connaît NI pdf.js NI le DOM : le chargeur de document et la
   fabrique de canvas sont INJECTÉS. Deux raisons, toutes deux structurelles :

   1. `UnderlayPdf.jsx` importe le worker pdf.js via le spécifieur Vite
      `pdfjs-dist/build/pdf.worker.min.mjs?worker` (empaqueté depuis NOTRE
      origine — jamais un CDN, exactement comme `features/ventes/PdfCanvas.jsx`).
      Ce spécifieur n'existe pas pour Node : un module qui l'importerait serait
      intestable par `node --test` (les fichiers *.test.mjs).
   2. La règle métier — quelle page, quelle rotation, quelle échelle, quand
      re-rastériser — est exactement ce qu'il faut verrouiller par test ; le
      dessin lui-même est l'affaire du navigateur.

   Principe de non-blocage : un plan de 20 pages n'est JAMAIS rastérisé en
   entier. pdf.js analyse le document dans son worker (hors thread principal),
   `listerPages` ne fait qu'en lire le nombre, et une SEULE page — celle
   sélectionnée — est peinte. */

/** Types acceptés comme plan source. Tout le reste dégrade avec un message FR. */
export const TYPES_PDF = ['application/pdf']
export const TYPES_IMAGE = ['image/png', 'image/jpeg', 'image/webp', 'image/gif', 'image/avif']

const EXT_PDF = /\.pdf$/i
const EXT_IMAGE = /\.(png|jpe?g|webp|gif|avif)$/i

function nomDe(fichier) {
  return (fichier && fichier.name) || ''
}
function typeDe(fichier) {
  return (fichier && fichier.type) || ''
}

export function estPdf(fichier) {
  return TYPES_PDF.includes(typeDe(fichier)) || EXT_PDF.test(nomDe(fichier))
}

export function estImageSupportee(fichier) {
  return TYPES_IMAGE.includes(typeDe(fichier)) || EXT_IMAGE.test(nomDe(fichier))
}

export function estFormatSupporte(fichier) {
  return estPdf(fichier) || estImageSupportee(fichier)
}

/** Message FR explicite (jamais une page blanche, jamais un code technique). */
export function messageFormatNonSupporte(fichier) {
  const nom = nomDe(fichier)
  const cible = nom ? `« ${nom} »` : 'Ce fichier'
  return (
    `${cible} n'est pas un fond de plan exploitable. Formats acceptés : PDF, PNG, JPEG, WebP, ` +
    `GIF ou AVIF. Pour un DXF, passez par l'import DXF (mapping des calques).`
  )
}

/** Rotation normalisée : multiple de 90° ramené dans [0, 360). */
export function normaliserRotation(deg) {
  const n = Number(deg)
  if (!Number.isFinite(n)) return 0
  const quart = Math.round(n / 90) * 90
  return ((quart % 360) + 360) % 360
}

/** Page bornée à [1, total] — un index hors plage ne doit jamais casser le rendu. */
export function bornerPage(numero, total) {
  const n = Math.trunc(Number(numero))
  const max = Math.max(1, Math.trunc(Number(total) || 1))
  if (!Number.isFinite(n) || n < 1) return 1
  return Math.min(n, max)
}

/**
 * Échelle de rendu : on remplit la largeur disponible, on tient compte du
 * rapport de pixels de l'écran, du zoom courant de l'atelier, et on borne pour
 * ne jamais fabriquer un canvas gigantesque (mémoire).
 */
export function facteurEchelle({ largeurDisponible, largeurPage, dpr = 1, zoom = 1, max = 6 }) {
  const dispo = Number(largeurDisponible)
  const page = Number(largeurPage)
  if (!Number.isFinite(dispo) || !Number.isFinite(page) || dispo <= 0 || page <= 0) return 1
  const d = Number.isFinite(dpr) && dpr > 0 ? Math.min(dpr, 2) : 1
  const z = Number.isFinite(zoom) && zoom > 0 ? zoom : 1
  return Math.min((dispo / page) * d * z, max)
}

/**
 * Re-rastériser au zoom ? On ne repeint que si l'échelle voulue dépasse
 * franchement l'échelle déjà rendue (sinon on repeindrait à chaque molette).
 * Dézoomer ne repeint jamais : l'image existante est simplement réduite.
 */
export function doitRerasteriser({ echelleRendue, echelleVoulue, hysteresis = 1.25 }) {
  const rendue = Number(echelleRendue)
  const voulue = Number(echelleVoulue)
  if (!Number.isFinite(rendue) || rendue <= 0) return true
  if (!Number.isFinite(voulue) || voulue <= 0) return false
  // `hysteresis` (et non « marge ») : facteur de repeinture d'AFFICHAGE, sans
  // rapport avec une marge métier — la garde AOF94 réserve ce mot au moteur.
  return voulue > rendue * hysteresis
}

/** Nombre de pages d'un document déjà ouvert — sans en peindre AUCUNE. */
export function listerPages(doc) {
  const total = Math.max(1, Math.trunc(Number(doc && doc.numPages) || 1))
  return Array.from({ length: total }, (_, i) => i + 1)
}

/**
 * Ouvre un document PDF. `charger` est injecté (en production :
 * `pdfjsLib.getDocument`), ce qui garde ce module hors du graphe pdf.js.
 * Les octets sont copiés par l'appelant : pdf.js peut « détacher » le buffer.
 */
export async function ouvrirDocument(charger, donnees) {
  if (typeof charger !== 'function') {
    throw new Error("Le lecteur PDF n'est pas disponible.")
  }
  const tache = charger({ data: donnees })
  return tache && tache.promise ? tache.promise : tache
}

/**
 * Peint UNE page sur un canvas et rend le descripteur du fond de calque.
 * Retourne l'échelle et la rotation effectivement rendues, pour que l'appelant
 * sache s'il devra re-rastériser plus tard.
 */
export async function rasteriserPage(doc, options = {}) {
  const {
    numeroPage = 1,
    rotation = 0,
    echelle = 1,
    creerCanvas,
    signalAnnule,
  } = options
  if (!doc || typeof doc.getPage !== 'function') {
    throw new Error("Le plan n'a pas pu être lu.")
  }
  const total = Math.max(1, Math.trunc(Number(doc.numPages) || 1))
  const numero = bornerPage(numeroPage, total)
  const rot = normaliserRotation(rotation)

  const page = await doc.getPage(numero)
  if (signalAnnule && signalAnnule()) return null
  const viewport = page.getViewport({ scale: echelle, rotation: rot })

  const fabrique =
    typeof creerCanvas === 'function'
      ? creerCanvas
      : () => globalThis.document.createElement('canvas')
  const canvas = fabrique()
  canvas.width = Math.max(1, Math.floor(viewport.width))
  canvas.height = Math.max(1, Math.floor(viewport.height))

  await page.render({ canvasContext: canvas.getContext('2d'), viewport }).promise
  if (signalAnnule && signalAnnule()) return null

  return {
    canvas,
    numeroPage: numero,
    rotation: rot,
    echelle,
    largeurPx: canvas.width,
    hauteurPx: canvas.height,
  }
}

/**
 * Libère tout ce qu'un fond de calque retient : le document pdf.js (worker +
 * caches de pages) et le canvas peint (un canvas de plan A0 pèse plusieurs
 * dizaines de Mo — le laisser attaché fuit à chaque changement de toiture).
 */
export function libererFond(fond) {
  if (!fond) return
  if (fond.doc && typeof fond.doc.destroy === 'function') {
    try {
      fond.doc.destroy()
    } catch {
      /* un document déjà détruit ne doit jamais casser le démontage */
    }
  }
  const canvas = fond.canvas
  if (canvas) {
    canvas.width = 0
    canvas.height = 0
  }
  if (fond.url && typeof URL !== 'undefined' && URL.revokeObjectURL) {
    try {
      URL.revokeObjectURL(fond.url)
    } catch {
      /* idem */
    }
  }
}
