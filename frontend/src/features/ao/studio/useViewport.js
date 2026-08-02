/* ============================================================================
   AOF74 — Algèbre de VUE d'un canvas exprimé en MÈTRES (x est→, y nord↑).
   ----------------------------------------------------------------------------
   ZÉRO nouvelle dépendance npm (contrainte VX) et — délibérément — ZÉRO import
   de React : la couche `*.test.mjs` du dépôt est exécutée par `node --test`
   (cf. `vitest.config.js` : « logique pure … distincte des tests de composants »),
   et AUCUN des 33 `*.test.mjs` existants n'importe React. Ce module est donc la
   MOITIÉ PURE du couple, exactement comme `pullToRefreshMath.js` l'est pour
   `usePullToRefresh.js` : il contient toutes les conversions écran↔monde, le pas
   de grille, les graduations, le niveau de détail — et un RÉDUCTEUR
   (`reduireViewport`) que `CanvasSvg.jsx` branche sur `useReducer`. La liaison
   React tient en quelques lignes dans `CanvasSvg.jsx` ; toute la logique
   testable vit ici.

   Repère : un `Viewport` est le RECTANGLE DE MONDE visible,
   `{ x, y, l, h }` en mètres, `(x, y)` = coin BAS-GAUCHE, `l`/`h` = largeur et
   hauteur. Le monde a y VERS LE NORD ; SVG a y vers le bas — d'où
   `viewBoxDe()`, qui rend un `viewBox` à utiliser AVEC un groupe racine
   `transform="scale(1,-1)"` (le seul endroit du fichier où la convention SVG
   apparaît).
   ========================================================================== */

// Bornes de zoom, en LARGEUR DE MONDE visible (mètres) : 50 cm de large = zoom
// maximal utile pour poser un sommet au centimètre ; 20 km = une commune.
export const LARGEUR_MIN_M = 0.5
export const LARGEUR_MAX_M = 20000

// Marge par défaut d'« ajuster à la vue » (6 % de chaque côté).
export const MARGE_AJUSTEMENT = 0.06

// Au-delà de ce nombre de tables PV, et TANT QUE le zoom reste large, la scène
// est rendue agrégée : un `<path>` par RANGÉE au lieu d'un par table (le rendu
// table-par-table ne réapparaît qu'au zoom). Un plan de 2 000 tables tombe
// ainsi à quelques dizaines de nœuds DOM.
export const SEUIL_AGREGATION = 400
export const SEUIL_DETAIL_PX_PAR_M = 8

const presqueEgal = (a, b, eps = 1e-9) => Math.abs(a - b) <= eps

function borner(v, min, max) {
  return Math.min(max, Math.max(min, v))
}

export function creerViewport(x = 0, y = 0, l = 100, h = 100) {
  return { x, y, l, h }
}

/** `viewBox` SVG correspondant — à poser sur `<svg>`, le contenu étant dans un
 *  groupe `transform="scale(1,-1)"` (monde y↑ → SVG y↓). */
export function viewBoxDe(vp) {
  return `${vp.x} ${-(vp.y + vp.h)} ${vp.l} ${vp.h}`
}

export function metresParPixel(vp, taille) {
  if (!(taille?.largeur > 0)) return 0
  return vp.l / taille.largeur
}

export function pixelsParMetre(vp, taille) {
  const mpp = metresParPixel(vp, taille)
  return mpp > 0 ? 1 / mpp : 0
}

/** Aligne l'aspect du viewport sur celui de l'élément, en ÉLARGISSANT toujours
 *  (jamais en rognant) et en gardant le centre : rien de visible ne disparaît. */
export function conformerAspect(vp, taille) {
  const largeur = taille?.largeur
  const hauteur = taille?.hauteur
  if (!(largeur > 0) || !(hauteur > 0) || !(vp.l > 0) || !(vp.h > 0)) return vp
  const aspectEcran = largeur / hauteur
  const aspectVue = vp.l / vp.h
  if (presqueEgal(aspectVue, aspectEcran, 1e-12)) return vp
  const cx = vp.x + vp.l / 2
  const cy = vp.y + vp.h / 2
  let l = vp.l
  let h = vp.h
  if (aspectVue < aspectEcran) l = vp.h * aspectEcran
  else h = vp.l / aspectEcran
  return { x: cx - l / 2, y: cy - h / 2, l, h }
}

/** Monde (m, y↑) → pixels CSS de l'élément (origine coin HAUT-gauche, y↓). */
export function mondeVersEcran(pt, vp, taille) {
  return {
    x: ((pt.x - vp.x) / vp.l) * taille.largeur,
    y: taille.hauteur - ((pt.y - vp.y) / vp.h) * taille.hauteur,
  }
}

/** Pixels CSS de l'élément → monde (m, y↑). Inverse EXACT de `mondeVersEcran`. */
export function ecranVersMonde(pt, vp, taille) {
  return {
    x: vp.x + (pt.x / taille.largeur) * vp.l,
    y: vp.y + ((taille.hauteur - pt.y) / taille.hauteur) * vp.h,
  }
}

/** Panoramique « le contenu suit le curseur » : un glissement de +dx pixels
 *  vers la droite fait glisser la fenêtre de monde vers la GAUCHE. */
export function deplacerPixels(vp, dxPx, dyPx, taille) {
  if (!(taille?.largeur > 0) || !(taille?.hauteur > 0)) return vp
  return {
    ...vp,
    x: vp.x - dxPx * (vp.l / taille.largeur),
    y: vp.y + dyPx * (vp.h / taille.hauteur),
  }
}

/** Zoom autour d'une ancre EN PIXELS : le point de monde sous l'ancre ne bouge
 *  pas d'un pixel (`facteur > 1` = on se rapproche). */
export function zoomerAutour(vp, facteur, ancrePx, taille) {
  if (!(facteur > 0) || !(taille?.largeur > 0) || !(taille?.hauteur > 0)) return vp
  const ancreMonde = ecranVersMonde(ancrePx, vp, taille)
  const l = borner(vp.l / facteur, LARGEUR_MIN_M, LARGEUR_MAX_M)
  const h = vp.h * (l / vp.l)
  const fx = ancrePx.x / taille.largeur
  const fy = (taille.hauteur - ancrePx.y) / taille.hauteur
  return { x: ancreMonde.x - fx * l, y: ancreMonde.y - fy * h, l, h }
}

export function zoomerAuCentre(vp, facteur, taille) {
  return zoomerAutour(vp, facteur, { x: taille.largeur / 2, y: taille.hauteur / 2 }, taille)
}

/** Boîte englobante d'un nuage de points de monde (`null` si vide). */
export function bboxDePoints(points = []) {
  const valides = points.filter((p) => Number.isFinite(p?.x) && Number.isFinite(p?.y))
  if (valides.length === 0) return null
  let xMin = Infinity
  let yMin = Infinity
  let xMax = -Infinity
  let yMax = -Infinity
  for (const p of valides) {
    if (p.x < xMin) xMin = p.x
    if (p.x > xMax) xMax = p.x
    if (p.y < yMin) yMin = p.y
    if (p.y > yMax) yMax = p.y
  }
  return { xMin, yMin, xMax, yMax }
}

/** « Ajuster à la vue » : la bbox entière tient à l'écran, marge comprise. */
export function ajusterAVue(bbox, taille, marge = MARGE_AJUSTEMENT) {
  if (!bbox || !(taille?.largeur > 0) || !(taille?.hauteur > 0)) return null
  const l0 = Math.max(bbox.xMax - bbox.xMin, 1e-3)
  const h0 = Math.max(bbox.yMax - bbox.yMin, 1e-3)
  const cx = (bbox.xMin + bbox.xMax) / 2
  const cy = (bbox.yMin + bbox.yMax) / 2
  const conforme = conformerAspect({ x: cx - l0 / 2, y: cy - h0 / 2, l: l0, h: h0 }, taille)
  const facteur = 1 + 2 * Math.max(0, marge)
  const l = borner(conforme.l * facteur, LARGEUR_MIN_M, LARGEUR_MAX_M)
  const h = conforme.h * (l / conforme.l)
  return { x: cx - l / 2, y: cy - h / 2, l, h }
}

/** Pas de grille ADAPTATIF sur l'échelle 1-2-5 : le pas « rond » dont l'écart à
 *  l'écran est le PLUS PROCHE de `ciblePx`. Le choix se fait sur l'échelle
 *  logarithmique (seuils = moyennes géométriques √2, √10, √50) — un arrondi
 *  systématique VERS LE HAUT ferait sauter d'un facteur 2,4 juste après 2 et la
 *  grille « respirerait » de façon visible au zoom. */
export function pasDeGrille(vp, taille, ciblePx = 64) {
  const mpp = metresParPixel(vp, taille)
  if (!(mpp > 0)) return 1
  const brut = Math.max(ciblePx * mpp, 1e-9)
  const exposant = Math.floor(Math.log10(brut))
  const base = 10 ** exposant
  const n = brut / base
  const multiplicateur = n < Math.SQRT2 ? 1 : n < Math.sqrt(10) ? 2 : n < Math.sqrt(50) ? 5 : 10
  return multiplicateur * base
}

const MAX_GRADUATIONS = 500

/** Coordonnées de monde des graduations visibles sur un axe (multiples du pas). */
export function graduations(vp, axe = 'x', pas = 1) {
  const debut = axe === 'x' ? vp.x : vp.y
  const etendue = axe === 'x' ? vp.l : vp.h
  if (!(pas > 0) || !(etendue > 0)) return []
  const premier = Math.ceil(debut / pas - 1e-9) * pas
  const out = []
  for (let i = 0; i < MAX_GRADUATIONS; i += 1) {
    const v = premier + i * pas
    if (v > debut + etendue + 1e-9) break
    // Le cumul flottant fait dériver « 12,000000000000002 » : on ré-arrondit
    // sur le pas pour que les libellés de règle restent ronds.
    out.push(Number((Math.round(v / pas) * pas).toFixed(6)))
  }
  return out
}

const nombreFr = (v, decimales) => v.toFixed(decimales).replace('.', ',')

/** Libellé d'un métrage pour la barre d'état/les règles (précision adaptée). */
export function formatMetres(v, pas = 1) {
  if (!Number.isFinite(v)) return '—'
  const decimales = pas >= 10 ? 0 : pas >= 1 ? 1 : pas >= 0.1 ? 2 : 3
  return `${nombreFr(v, decimales)} m`
}

/** Échelle courante, lisible : « 1 m = 12,4 px » ou « 1 px = 2,3 m » au large. */
export function texteEchelle(vp, taille) {
  const ppm = pixelsParMetre(vp, taille)
  if (!(ppm > 0)) return '—'
  if (ppm >= 1) return `1 m = ${nombreFr(ppm, 1)} px`
  return `1 px = ${nombreFr(1 / ppm, 1)} m`
}

/** Niveau de détail : au large ET au-delà du seuil, on agrège par rangée. */
export function doitAgreger(nbTables, vp, taille, seuil = SEUIL_AGREGATION) {
  if (!(nbTables > seuil)) return false
  return pixelsParMetre(vp, taille) < SEUIL_DETAIL_PX_PAR_M
}

/** Agrège des tables `{ id, rangee, d }` en UN chemin par rangée. */
export function agregerParRangee(tables = []) {
  const parRangee = new Map()
  for (const t of tables) {
    if (!t?.d) continue
    const cle = t.rangee ?? 'hors-rangee'
    if (!parRangee.has(cle)) parRangee.set(cle, [])
    parRangee.get(cle).push(t.d)
  }
  return [...parRangee.entries()].map(([rangee, ds]) => ({ rangee, d: ds.join(' ') }))
}

/* ── Réducteur : l'ÉTAT de vue, sans une ligne de React ─────────────────────
   `CanvasSvg.jsx` fait `useReducer(reduireViewport, …)` ; tout le comportement
   testé ci-dessus est donc exercé par `node --test`, pas par un rendu. */
export function reduireViewport(etat, action) {
  const { viewport: vp, taille } = etat
  switch (action.type) {
    case 'taille': {
      const nouvelle = action.taille
      if (!(nouvelle?.largeur > 0) || !(nouvelle?.hauteur > 0)) return etat
      return { taille: nouvelle, viewport: conformerAspect(vp, nouvelle) }
    }
    case 'deplacer':
      return { ...etat, viewport: deplacerPixels(vp, action.dx, action.dy, taille) }
    case 'zoom':
      return {
        ...etat,
        viewport: action.ancre
          ? zoomerAutour(vp, action.facteur, action.ancre, taille)
          : zoomerAuCentre(vp, action.facteur, taille),
      }
    case 'ajuster': {
      const ajuste = ajusterAVue(action.bbox, taille, action.marge)
      return ajuste ? { ...etat, viewport: ajuste } : etat
    }
    case 'poser':
      return { ...etat, viewport: conformerAspect(action.viewport, taille) }
    default:
      return etat
  }
}

export default {
  creerViewport,
  viewBoxDe,
  mondeVersEcran,
  ecranVersMonde,
  reduireViewport,
}
