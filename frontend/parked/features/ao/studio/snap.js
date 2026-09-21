// Extension `.js` EXPLICITE : ce module est chargé par `node --test` via
// `snap.test.mjs` (ESM strict — l'extension n'y est jamais devinée), pas
// seulement par Vite.
import { bboxDePoints } from './useViewport.js'

/* ============================================================================
   AOF76 — Accrochage, transformations et GARDE DE VALIDITÉ géométrique.
   ----------------------------------------------------------------------------
   Module PUR (aucun React, aucun DOM) : c'est ici que vit tout ce que
   `Selection.jsx` se contente de rendre, et c'est ici que `snap.test.mjs`
   (node:test) prouve la règle centrale du contrat — AUCUNE manipulation à la
   souris ne peut produire une géométrie invalide.

   La garde d'auto-intersection est le JUMEAU côté ERP du garde W76 du traceur
   public (`apps/web/src/lib/roof.ts::isSimplePolygon`, croisement PROPRE par
   produits vectoriels). `apps/web` n'est JAMAIS modifié depuis un run
   plateforme : la logique est ré-écrite ici sur le repère AO (`{x, y}` en
   mètres, y↑) au lieu d'être importée d'un autre bundle.

   Ordre de priorité de l'accrochage — un ordre, pas un empilement :
     1. SOMMET (l'intention la plus forte : fermer sur un point existant) ;
     2. ANGLE remarquable depuis l'ancre (les angles droits d'un bâtiment) ;
     3. ALIGNEMENT sur x et/ou y d'une référence (les deux axes indépendamment).
   ========================================================================== */

export const TOLERANCE_ACCROCHAGE_PX = 10
export const PAS_ANGLE_DEG = 45
export const MIN_SOMMETS = 3

export function distance(a, b) {
  return Math.hypot(a.x - b.x, a.y - b.y)
}

/** Croisement PROPRE de deux segments (contacts par extrémité NON comptés). */
export function segmentsSeCroisent(p1, p2, p3, p4) {
  const cross = (a, b, c) => (b.x - a.x) * (c.y - a.y) - (b.y - a.y) * (c.x - a.x)
  const d1 = cross(p3, p4, p1)
  const d2 = cross(p3, p4, p2)
  const d3 = cross(p1, p2, p3)
  const d4 = cross(p1, p2, p4)
  return ((d1 > 0) !== (d2 > 0)) && ((d3 > 0) !== (d4 > 0))
}

/** Vrai si l'anneau FERMÉ n'a aucun « nœud papillon ». < 4 sommets ⇒ vrai. */
export function polygoneSimple(points) {
  if (!Array.isArray(points) || points.length < 4) return true
  const n = points.length
  for (let i = 0; i < n; i += 1) {
    const a1 = points[i]
    const a2 = points[(i + 1) % n]
    for (let j = i + 2; j < n; j += 1) {
      if (i === 0 && j === n - 1) continue
      if (segmentsSeCroisent(a1, a2, points[j], points[(j + 1) % n])) return false
    }
  }
  return true
}

export function aireSignee(points) {
  if (!Array.isArray(points) || points.length < 3) return 0
  let somme = 0
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    somme += a.x * b.y - b.x * a.y
  }
  return somme / 2
}

export function aire(points) {
  return Math.abs(aireSignee(points))
}

export function perimetre(points) {
  if (!Array.isArray(points) || points.length < 2) return 0
  let total = 0
  for (let i = 0; i < points.length; i += 1) {
    total += distance(points[i], points[(i + 1) % points.length])
  }
  return total
}

/** Azimut (° depuis le nord, sens horaire) de l'arête la plus longue. */
export function azimutAretePrincipale(points) {
  if (!Array.isArray(points) || points.length < 2) return null
  let meilleure = null
  let longueur = -1
  for (let i = 0; i < points.length; i += 1) {
    const a = points[i]
    const b = points[(i + 1) % points.length]
    const d = distance(a, b)
    if (d > longueur) {
      longueur = d
      meilleure = { a, b }
    }
  }
  if (!meilleure || longueur <= 0) return null
  const { a, b } = meilleure
  const deg = (Math.atan2(b.x - a.x, b.y - a.y) * 180) / Math.PI
  return ((deg % 360) + 360) % 360
}

/* ── Garde de validité ─────────────────────────────────────────────────────
   Une seule porte : toute transformation passe par `appliquerSiValide`. */

export const RAISONS = {
  auto_intersection: 'Le contour se croiserait (nœud papillon) — déplacement refusé.',
  trop_peu_de_sommets: 'Un contour a besoin d’au moins 3 sommets.',
  aire_nulle: 'Le contour serait aplati (aire nulle) — déplacement refusé.',
}

export function verifierGeometrie(points) {
  if (!Array.isArray(points) || points.length < MIN_SOMMETS) {
    return { valide: false, raison: 'trop_peu_de_sommets' }
  }
  if (!points.every((p) => Number.isFinite(p?.x) && Number.isFinite(p?.y))) {
    return { valide: false, raison: 'trop_peu_de_sommets' }
  }
  if (!polygoneSimple(points)) return { valide: false, raison: 'auto_intersection' }
  if (aire(points) < 1e-6) return { valide: false, raison: 'aire_nulle' }
  return { valide: true, raison: null }
}

/**
 * LA porte : rend la géométrie transformée si elle est valide, sinon rend
 * l'ANCIENNE inchangée avec le motif du refus. Aucun appelant ne peut donc
 * écrire une géométrie invalide, même par erreur.
 */
export function appliquerSiValide(avant, apres) {
  const v = verifierGeometrie(apres)
  if (!v.valide) return { points: avant, valide: false, raison: v.raison, message: RAISONS[v.raison] }
  return { points: apres, valide: true, raison: null, message: null }
}

/* ── Transformations pures ────────────────────────────────────────────────── */

export function deplacerPoints(points, indices, delta) {
  const cibles = new Set(indices ?? [])
  return points.map((p, i) => (cibles.has(i) ? { ...p, x: p.x + delta.dx, y: p.y + delta.dy } : p))
}

/** Applique la transformation affine qui envoie `boiteAvant` sur `boiteApres`. */
export function redimensionnerPoints(points, boiteAvant, boiteApres) {
  const lA = boiteAvant.xMax - boiteAvant.xMin
  const hA = boiteAvant.yMax - boiteAvant.yMin
  if (!(lA > 0) || !(hA > 0)) return points
  const sx = (boiteApres.xMax - boiteApres.xMin) / lA
  const sy = (boiteApres.yMax - boiteApres.yMin) / hA
  return points.map((p) => ({
    ...p,
    x: boiteApres.xMin + (p.x - boiteAvant.xMin) * sx,
    y: boiteApres.yMin + (p.y - boiteAvant.yMin) * sy,
  }))
}

export function pivoterPoints(points, centre, angleRad) {
  const c = Math.cos(angleRad)
  const s = Math.sin(angleRad)
  return points.map((p) => {
    const dx = p.x - centre.x
    const dy = p.y - centre.y
    return { ...p, x: centre.x + dx * c - dy * s, y: centre.y + dx * s + dy * c }
  })
}

export function centreDe(points) {
  const b = bboxDePoints(points)
  if (!b) return null
  return { x: (b.xMin + b.xMax) / 2, y: (b.yMin + b.yMax) / 2 }
}

/* ── Accrochage ────────────────────────────────────────────────────────────── */

/** Accroche au sommet existant le plus proche, dans la tolérance. */
export function accrocherSommet(pt, sommets = [], tolerance = 0.25) {
  let meilleur = null
  let meilleureD = Infinity
  for (const s of sommets) {
    if (!Number.isFinite(s?.x) || !Number.isFinite(s?.y)) continue
    const d = distance(pt, s)
    if (d <= tolerance && d < meilleureD) {
      meilleureD = d
      meilleur = s
    }
  }
  if (!meilleur) return null
  return {
    point: { x: meilleur.x, y: meilleur.y },
    guides: [{ type: 'sommet', x: meilleur.x, y: meilleur.y }],
  }
}

/** Accroche un angle remarquable depuis l'ancre (angles droits d'un bâtiment). */
export function accrocherAngle(pt, ancre, tolerance = 0.25, pasDeg = PAS_ANGLE_DEG) {
  if (!ancre || !(pasDeg > 0)) return null
  const dx = pt.x - ancre.x
  const dy = pt.y - ancre.y
  const rayon = Math.hypot(dx, dy)
  if (rayon < 1e-9) return null
  const pas = (pasDeg * Math.PI) / 180
  const angle = Math.atan2(dy, dx)
  const cible = Math.round(angle / pas) * pas
  // Écart PERPENDICULAIRE au rayon : à 30 m de l'ancre, 1° fait déjà 0,5 m —
  // une tolérance angulaire fixe accrocherait de force au loin.
  if (rayon * Math.abs(Math.sin(angle - cible)) > tolerance) return null
  const point = { x: ancre.x + rayon * Math.cos(cible), y: ancre.y + rayon * Math.sin(cible) }
  const degres = ((Math.round((cible * 180) / Math.PI) % 360) + 360) % 360
  return { point, guides: [{ type: 'angle', ancre, point, degres }] }
}

/** Aligne x et/ou y (indépendamment) sur une référence à portée. */
export function accrocherAlignement(pt, references = [], tolerance = 0.25) {
  let x = null
  let y = null
  let dx = Infinity
  let dy = Infinity
  for (const r of references) {
    if (!Number.isFinite(r?.x) || !Number.isFinite(r?.y)) continue
    const ex = Math.abs(pt.x - r.x)
    if (ex <= tolerance && ex < dx) { dx = ex; x = r.x }
    const ey = Math.abs(pt.y - r.y)
    if (ey <= tolerance && ey < dy) { dy = ey; y = r.y }
  }
  if (x == null && y == null) return null
  const guides = []
  if (x != null) guides.push({ type: 'alignement', axe: 'x', valeur: x })
  if (y != null) guides.push({ type: 'alignement', axe: 'y', valeur: y })
  return { point: { x: x ?? pt.x, y: y ?? pt.y }, guides }
}

/**
 * Orchestrateur : rend `{ point, guides, accroche }`. `accroche` vaut `null`
 * quand rien n'a mordu — le point est alors rendu tel quel (jamais `null`).
 */
export function accrocher(pt, contexte = {}) {
  const {
    actif = true,
    sommets = [],
    references = [],
    ancre = null,
    tolerance = 0.25,
    pasAngle = PAS_ANGLE_DEG,
  } = contexte
  if (!actif) return { point: pt, guides: [], accroche: null }

  const surSommet = accrocherSommet(pt, sommets, tolerance)
  if (surSommet) return { ...surSommet, accroche: 'sommet' }

  const surAngle = accrocherAngle(pt, ancre, tolerance, pasAngle)
  if (surAngle) return { ...surAngle, accroche: 'angle' }

  const surAlignement = accrocherAlignement(pt, references, tolerance)
  if (surAlignement) return { ...surAlignement, accroche: 'alignement' }

  return { point: pt, guides: [], accroche: null }
}

/** Tolérance d'accrochage en MÈTRES à partir d'une tolérance écran en pixels. */
export function toleranceMetres(metresParPixel, pixels = TOLERANCE_ACCROCHAGE_PX) {
  return Math.max(metresParPixel * pixels, 1e-6)
}

/* ── Sélection ─────────────────────────────────────────────────────────────── */

export function rectangleDe(a, b) {
  return {
    xMin: Math.min(a.x, b.x),
    yMin: Math.min(a.y, b.y),
    xMax: Math.max(a.x, b.x),
    yMax: Math.max(a.y, b.y),
  }
}

export function dansRectangle(pt, rect) {
  return pt.x >= rect.xMin && pt.x <= rect.xMax && pt.y >= rect.yMin && pt.y <= rect.yMax
}

export function indicesDansRectangle(points = [], rect) {
  const out = []
  points.forEach((p, i) => {
    if (dansRectangle(p, rect)) out.push(i)
  })
  return out
}

/** Maj+clic = bascule dans la sélection ; clic simple = sélection unique. */
export function basculerSelection(selection = [], index, multiple = false) {
  if (!multiple) return [index]
  return selection.includes(index)
    ? selection.filter((i) => i !== index)
    : [...selection, index].sort((a, b) => a - b)
}

export default {
  accrocher,
  appliquerSiValide,
  polygoneSimple,
  verifierGeometrie,
}
