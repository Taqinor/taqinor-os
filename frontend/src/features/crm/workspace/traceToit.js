/* L-DESSIN (ordre fondateur 25/08/2026 : « when the client draws his roof i
   still do not receive the drawing ») — RENDU du tracé de toit dessiné par le
   client dans le tunnel public.
   ---------------------------------------------------------------------------
   La donnée arrivait déjà : le tunnel envoie `roofOutline` (mon-toit.astro),
   le webhook la range dans `crm.Lead.roof_outline` (webhooks.py), la fiche la
   sert (`LeadSerializer`, fields='__all__'). Mais l'ERP n'en faisait qu'un
   BADGE texte (« ⬠ Contour tracé ») : le commercial — et le fondateur — ne
   voyaient JAMAIS le dessin. Ce module transforme le contour en une FORME
   affichable, sans carte, sans clé MapTiler, sans réseau : un polygone SVG.

   ORDRE DES AXES — la règle du dépôt (apps/ao/geometrie.py, repere.js) :
   `Lead.roof_outline` est en **[lat, lng]** (latitude d'abord). On le déclare
   à chaque frontière (`ORDRE_LATLNG`) plutôt que de le deviner : une inversion
   est silencieuse (le polygone reste plausible, il atterrit à 800 km).

   AUCUN CHIFFRE INVENTÉ : la surface et l'emprise rendues ici sont CALCULÉES
   sur les sommets réels du client (projection locale métrique de `repere.js`,
   déjà utilisée par l'atelier AO) ; sans contour exploitable, ce module rend
   `null` et l'écran n'affiche rien — jamais un « 0 m² » ni une forme par
   défaut. */
import {
  ORDRE_LATLNG, aireM2, contourVersSommetsM, creerRepere,
// Extension EXPLICITE : ce module est chargé tel quel par `node --test`
// (`src/**/*.test.mjs`), qui ne résout pas les imports sans extension.
} from '../../ao/toiture/repere.js'

/** Côté maximal du dessin, en unités de viewBox SVG (le rendu est responsive). */
export const COTE_DESSIN = 200

const borne = (v, min, max) => Number.isFinite(v) && v >= min && v <= max

/**
 * Contour brut du lead → liste de `[lat, lng]` finis et plausibles.
 * Tolère les deux formes rencontrées en base : `[[lat, lng], …]` (webhook) et
 * `[{lat, lng}, …]`. Moins de 3 sommets valides ⇒ `[]` (ce n'est pas un
 * polygone) — MÊME règle que `_clean_roof_outline` côté webhook.
 */
export function normaliserContour(brut) {
  if (!Array.isArray(brut)) return []
  const points = []
  for (const p of brut) {
    let lat
    let lng
    if (Array.isArray(p) && p.length >= 2) {
      lat = Number(p[0])
      lng = Number(p[1])
    } else if (p && typeof p === 'object') {
      lat = Number(p.lat)
      lng = Number(p.lng)
    } else {
      continue
    }
    if (borne(lat, -90, 90) && borne(lng, -180, 180)) points.push([lat, lng])
  }
  return points.length >= 3 ? points : []
}

/** Épingle brute du lead (`{lat, lng}`) → `{lat, lng}` finis, sinon `null`. */
export function normaliserEpingle(brut) {
  if (!brut || typeof brut !== 'object') return null
  const lat = Number(brut.lat)
  const lng = Number(brut.lng)
  if (!borne(lat, -90, 90) || !borne(lng, -180, 180)) return null
  return { lat, lng }
}

/** Centre du tracé (moyenne des sommets) — jamais une position inventée. */
export function centreContour(points) {
  if (!Array.isArray(points) || points.length === 0) return null
  let lat = 0
  let lng = 0
  for (const [a, o] of points) {
    lat += a
    lng += o
  }
  return { lat: lat / points.length, lng: lng / points.length }
}

/**
 * Contour du lead → tout ce qu'il faut pour l'afficher :
 *   { points, largeur, hauteur, sommets, aireM2, largeurM, hauteurM, centre }
 * `points` est la chaîne `points=""` d'un `<polygon>` SVG, NORD EN HAUT
 * (l'axe y du SVG descend, on le renverse), à l'échelle et sans déformation.
 * Rend `null` dès que le contour n'est pas exploitable (moins de 3 sommets,
 * ou emprise nulle : trois clics au même endroit).
 */
export function dessinerContour(brut) {
  const points = normaliserContour(brut)
  if (points.length < 3) return null
  let sommets
  try {
    const repere = creerRepere({ origine_lnglat: [points[0][1], points[0][0]] })
    sommets = contourVersSommetsM(repere, points, ORDRE_LATLNG)
  } catch {
    return null // coordonnées refusées par le repère : on n'affiche rien.
  }
  const xs = sommets.map((s) => s.x)
  const ys = sommets.map((s) => s.y)
  const minX = Math.min(...xs)
  const maxX = Math.max(...xs)
  const minY = Math.min(...ys)
  const maxY = Math.max(...ys)
  const largeurM = maxX - minX
  const hauteurM = maxY - minY
  const etendue = Math.max(largeurM, hauteurM)
  if (!Number.isFinite(etendue) || etendue <= 0) return null
  const echelle = COTE_DESSIN / etendue
  return {
    points: sommets
      .map((s) => `${((s.x - minX) * echelle).toFixed(1)},${((maxY - s.y) * echelle).toFixed(1)}`)
      .join(' '),
    largeur: Math.max(1, Number((largeurM * echelle).toFixed(1))),
    hauteur: Math.max(1, Number((hauteurM * echelle).toFixed(1))),
    sommets: points.length,
    aireM2: aireM2(sommets),
    largeurM,
    hauteurM,
    centre: centreContour(points),
  }
}

/** Arrondi d'affichage d'une surface — jamais « 0 m² » pour une vraie surface. */
export function formaterSurface(m2) {
  if (!Number.isFinite(m2) || m2 <= 0) return null
  if (m2 < 10) return `${m2.toFixed(1)} m²`
  return `${Math.round(m2)} m²`
}

/** Lien carte — MÊME forme que le lien GPS déjà servi par IdentityRail. */
export function lienCarte(position) {
  const p = normaliserEpingle(position)
  return p ? `https://www.google.com/maps?q=${p.lat},${p.lng}` : null
}
