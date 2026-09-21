/* ============================================================================
   AOF75 — Export d'une vue d'atelier en image (SVG → PNG).
   ----------------------------------------------------------------------------
   Brique PARTAGÉE, construite une fois : la miniature de plan du comparateur
   (AOF102), l'export en image de l'échelle de décomposition (AOF104) et
   l'image de fond de l'annotateur Q/R (AOF106) en dépendent tous — sans elle,
   chacun la réinventerait légèrement différemment.

   Zéro dépendance externe : sérialisation du `<svg>` + rendu dans un
   `<canvas>` à résolution paramétrable et BORNÉE.

   LE PIÈGE, ET LA RAISON D'ÊTRE DE CE FICHIER : un SVG sérialisé puis chargé
   dans une `<img>` est un DOCUMENT ISOLÉ — il n'a accès ni à la feuille de
   styles de l'application, ni aux custom-properties de `:root`. Un
   `fill="var(--primary)"` ou une classe Tailwind y perdent leur valeur et le
   navigateur retombe sur NOIR. On inline donc, avant sérialisation, les
   propriétés calculées qui comptent (elles sont déjà résolues par le moteur),
   puis on balaie une dernière fois le texte pour qu'AUCUN `var(--…)` ne
   subsiste.

   Second parti pris : tout export destiné à un DOCUMENT est rendu en thème
   CLAIR, sur fond opaque. Une planche exportée depuis un écran sombre serait
   illisible une fois collée dans un dossier de soumission, et un PNG
   transparent devient noir dans la plupart des visionneuses PDF.
   ========================================================================== */

export const LARGEUR_EXPORT_DEFAUT = 1000
export const MAX_PIXELS_EXPORT = 4096
export const FOND_DOCUMENT = '#ffffff'

// Propriétés dont la perte se VOIT (couleur, trait, police). `getComputedStyle`
// les rend déjà résolues — c'est ce qui casse la chaîne des custom-properties.
export const PROPRIETES_INLINE = [
  'fill',
  'fill-opacity',
  'fill-rule',
  'stroke',
  'stroke-width',
  'stroke-opacity',
  'stroke-dasharray',
  'stroke-linecap',
  'stroke-linejoin',
  'vector-effect',
  'opacity',
  'color',
  'font-family',
  'font-size',
  'font-weight',
  'font-style',
  'letter-spacing',
  'text-anchor',
  'dominant-baseline',
  'display',
  'visibility',
]

const VAR_UNIQUE = /var\(\s*(--[A-Za-z0-9_-]+)\s*(?:,([^()]*))?\)/
const VAR_RESTANTE = /var\([^()]*\)/g

/** Vrai s'il subsiste une custom-property non résolue dans le texte. */
export function contientVariableCss(texte) {
  return typeof texte === 'string' && /var\(\s*--/.test(texte)
}

/**
 * Remplace TOUT `var(--x[, repli])` par une valeur concrète.
 * `resolveur(nom)` rend la valeur du token, ou `null`/`undefined` s'il l'ignore
 * (on prend alors le repli écrit dans le `var()`, sinon `defaut`).
 * Les imbrications (`var(--a, var(--b, #fff))`) sont résolues de l'intérieur
 * vers l'extérieur ; `maxPasses` empêche une définition cyclique de boucler, et
 * un dernier balayage garantit qu'il ne reste JAMAIS un `var(` en sortie.
 */
export function resoudreVariablesCss(texte, resolveur, options = {}) {
  const { defaut = 'currentColor', maxPasses = 50 } = options
  if (typeof texte !== 'string') return ''
  let sortie = texte
  for (let i = 0; i < maxPasses; i += 1) {
    const m = VAR_UNIQUE.exec(sortie)
    if (!m) break
    const brut = resolveur ? resolveur(m[1]) : null
    const repli = m[2] != null && m[2].trim() !== '' ? m[2].trim() : defaut
    const valeur = brut != null && String(brut).trim() !== '' ? String(brut).trim() : repli
    sortie = sortie.slice(0, m.index) + valeur + sortie.slice(m.index + m[0].length)
  }
  return sortie.replace(VAR_RESTANTE, defaut)
}

/** Résolveur pur à partir d'une table de tokens (tests, rendu serveur, replis). */
export function resolveurFixe(tokens = {}) {
  return (nom) => tokens[nom] ?? null
}

/** Résolveur lisant les custom-properties RÉELLES d'un élément (navigateur). */
export function resolveurDuDocument(racine) {
  if (typeof window === 'undefined' || typeof window.getComputedStyle !== 'function') {
    return () => null
  }
  const el = racine ?? document.documentElement
  const style = window.getComputedStyle(el)
  return (nom) => {
    const v = style.getPropertyValue(nom)
    return v && v.trim() !== '' ? v.trim() : null
  }
}

/** Dimensions d'export : largeur demandée, ratio conservé, taille BORNÉE. */
export function dimensionsExport(source, options = {}) {
  const { largeur = LARGEUR_EXPORT_DEFAUT, maxPixels = MAX_PIXELS_EXPORT } = options
  const lSrc = Number(source?.largeur) > 0 ? Number(source.largeur) : 1
  const hSrc = Number(source?.hauteur) > 0 ? Number(source.hauteur) : 1
  const ratio = hSrc / lSrc
  let l = Math.max(1, Math.round(Math.min(Math.max(largeur, 1), maxPixels)))
  let h = Math.max(1, Math.round(l * ratio))
  if (h > maxPixels) {
    h = maxPixels
    l = Math.max(1, Math.round(h / ratio))
  }
  return { largeur: l, hauteur: h }
}

/* ── Partie DOM ────────────────────────────────────────────────────────────
   Séparée des fonctions pures ci-dessus : celles-ci sont testées au node
   (`svgToPng.test.mjs`), celles-là ne s'exécutent qu'en navigateur. */

function forcerThemeClair() {
  if (typeof document === 'undefined') return () => {}
  const racine = document.documentElement
  const avant = racine.getAttribute('data-theme')
  racine.setAttribute('data-theme', 'light')
  return () => {
    if (avant == null) racine.removeAttribute('data-theme')
    else racine.setAttribute('data-theme', avant)
  }
}

function inlinerStyles(source, clone) {
  if (typeof window === 'undefined' || typeof window.getComputedStyle !== 'function') return
  const originaux = [source, ...source.querySelectorAll('*')]
  const copies = [clone, ...clone.querySelectorAll('*')]
  for (let i = 0; i < originaux.length && i < copies.length; i += 1) {
    const calcule = window.getComputedStyle(originaux[i])
    const morceaux = []
    for (const prop of PROPRIETES_INLINE) {
      const v = calcule.getPropertyValue(prop)
      if (v && v.trim() !== '') morceaux.push(`${prop}:${v.trim()}`)
    }
    copies[i].setAttribute('style', morceaux.join(';'))
    // Les classes utilitaires ne servent plus à rien dans un document isolé —
    // les garder ne ferait qu'alourdir la chaîne sérialisée.
    copies[i].removeAttribute('class')
  }
}

/**
 * Sérialise un `<svg>` en document AUTONOME : styles inlinés, tokens résolus,
 * dimensions explicites. Le résultat ne contient aucun `var(--…)`.
 */
export function serialiserSvg(svgEl, options = {}) {
  if (!svgEl) return ''
  const restaurer = options.themeClair === false ? () => {} : forcerThemeClair()
  try {
    const clone = svgEl.cloneNode(true)
    inlinerStyles(svgEl, clone)
    const boite = svgEl.getBoundingClientRect?.() ?? { width: 0, height: 0 }
    const dims = dimensionsExport(
      { largeur: boite.width || 1, hauteur: boite.height || 1 },
      options,
    )
    clone.setAttribute('xmlns', 'http://www.w3.org/2000/svg')
    clone.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink')
    clone.setAttribute('width', String(dims.largeur))
    clone.setAttribute('height', String(dims.hauteur))
    const brut = new XMLSerializer().serializeToString(clone)
    const resolveur = options.resolveur ?? resolveurDuDocument(svgEl)
    return resoudreVariablesCss(brut, resolveur, { defaut: options.couleurDefaut ?? '#000000' })
  } finally {
    restaurer()
  }
}

async function chargerImage(url) {
  return new Promise((resoudre, rejeter) => {
    const img = new Image()
    img.onload = () => resoudre(img)
    img.onerror = () => rejeter(new Error("Impossible de rendre l'aperçu du plan."))
    img.src = url
  })
}

/**
 * Rend un `<svg>` en PNG (data-URL) à `largeur` pixels de large, fond opaque.
 * Rend `{ dataUrl, largeur, hauteur }`.
 */
export async function svgVersPng(svgEl, options = {}) {
  if (!svgEl || typeof document === 'undefined') {
    throw new Error("Aucune vue à exporter.")
  }
  const texte = serialiserSvg(svgEl, options)
  const boite = svgEl.getBoundingClientRect?.() ?? { width: 1, height: 1 }
  const dims = dimensionsExport({ largeur: boite.width || 1, hauteur: boite.height || 1 }, options)
  const img = await chargerImage(
    `data:image/svg+xml;charset=utf-8,${encodeURIComponent(texte)}`,
  )
  const canvas = document.createElement('canvas')
  canvas.width = dims.largeur
  canvas.height = dims.hauteur
  const ctx = canvas.getContext('2d')
  ctx.fillStyle = options.fond ?? FOND_DOCUMENT
  ctx.fillRect(0, 0, dims.largeur, dims.hauteur)
  ctx.drawImage(img, 0, 0, dims.largeur, dims.hauteur)
  return { dataUrl: canvas.toDataURL('image/png'), ...dims }
}

/** Même rendu, en `Blob` (téléchargement, envoi multipart). */
export async function svgVersPngBlob(svgEl, options = {}) {
  const { dataUrl, largeur, hauteur } = await svgVersPng(svgEl, options)
  const reponse = await fetch(dataUrl)
  const blob = await reponse.blob()
  return { blob, largeur, hauteur }
}

export default svgVersPng
