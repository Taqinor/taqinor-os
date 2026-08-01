/* AOF83 — CONTRAT DE COORDONNÉES de l'atelier Toiture.
   ============================================================================
   ORDRE DES AXES — DÉCLARÉ, JAMAIS DEVINÉ.
   ----------------------------------------------------------------------------
   Le dépôt porte les DEUX ordres, et c'est un bug latent identifié :
     • le lecteur de cartes manipule des `LngLat = [lng, lat]` en interne ;
     • `roof_outline` du lead CRM (et `bootCaptureOnly.onCaptureChange.outline`)
       est en `[lat, lng]`.
   Un tableau de deux nombres ne dit PAS lequel des deux il est. Ce module refuse
   donc toute paire dont l'ordre n'est pas déclaré : soit on passe un objet nommé
   (`{ lng, lat }`), soit on passe `ORDRE_LNGLAT` / `ORDRE_LATLNG` explicitement.
   Une paire nue sans ordre lève — c'est voulu, et c'est testé.

   NOMS DE CHAMPS — également déclaratifs :
     • `origine_lnglat` : l'origine du repère local, TOUJOURS [lng, lat] ;
     • `azimut_deg`     : orientation de l'axe +y local, en degrés depuis le NORD
                          géographique, sens horaire (azimut au sens topographe) ;
     • `sommets_m`      : sommets en MÈTRES locaux { x, y } — x vers la droite du
                          repère, y vers le haut (ENU tourné de l'azimut).
   Aucun champ ne s'appelle « coords », « points » ou « xy » : un nom neutre est
   exactement ce qui a produit l'inversion qu'on corrige ici.

   PROJECTION : plan tangent local (ENU) sur l'ellipsoïde WGS84, avec les rayons
   de courbure exacts à la latitude de l'origine. Sur l'emprise d'une toiture
   (quelques centaines de mètres) l'erreur de planéité est très inférieure au
   millimètre, et l'aller-retour est l'inverse algébrique exact. */

const A_WGS84 = 6378137.0
const F_WGS84 = 1 / 298.257223563
const E2 = F_WGS84 * (2 - F_WGS84)
const RAD = Math.PI / 180

export const ORDRE_LNGLAT = 'lnglat'
export const ORDRE_LATLNG = 'latlng'

/**
 * Normalise une paire en `[lng, lat]`.
 * @param {[number,number]|{lng:number,lat:number}} paire
 * @param {'lnglat'|'latlng'} [ordre] OBLIGATOIRE pour un tableau ; interdit de
 *        l'omettre — une paire nue est ambiguë et lève.
 * @returns {[number, number]} `[lng, lat]`, dans CET ordre.
 */
export function versLngLat(paire, ordre) {
  if (paire && typeof paire === 'object' && !Array.isArray(paire)) {
    const lng = Number(paire.lng ?? paire.longitude)
    const lat = Number(paire.lat ?? paire.latitude)
    if (!Number.isFinite(lng) || !Number.isFinite(lat)) {
      throw new TypeError('Point invalide : `lng` et `lat` doivent être des nombres.')
    }
    return controler([lng, lat])
  }
  if (!Array.isArray(paire) || paire.length !== 2) {
    throw new TypeError('Point invalide : attendu [a, b] ou { lng, lat }.')
  }
  if (ordre !== ORDRE_LNGLAT && ordre !== ORDRE_LATLNG) {
    throw new TypeError(
      "Ordre des axes non déclaré : passez ORDRE_LNGLAT ('lnglat') ou ORDRE_LATLNG " +
        "('latlng'). Une paire de nombres nue est ambiguë — c'est exactement " +
        'l’inversion lng/lat que ce module existe pour empêcher.',
    )
  }
  const a = Number(paire[0])
  const b = Number(paire[1])
  if (!Number.isFinite(a) || !Number.isFinite(b)) {
    throw new TypeError('Point invalide : les deux composantes doivent être des nombres.')
  }
  return controler(ordre === ORDRE_LNGLAT ? [a, b] : [b, a])
}

/* Contrôle de domaine : une latitude hors [-90, 90] signale presque toujours un
   ordre déclaré à l'envers. On le dit franchement plutôt que de projeter du faux. */
function controler([lng, lat]) {
  if (lat < -90 || lat > 90) {
    throw new RangeError(
      `Latitude hors domaine (${lat}) : l'ordre des axes déclaré est probablement inversé.`,
    )
  }
  if (lng < -180 || lng > 180) {
    throw new RangeError(`Longitude hors domaine (${lng}).`)
  }
  return [lng, lat]
}

/** Sérialise `[lng, lat]` dans l'ordre demandé (pour rendre au CRM ou au tool). */
export function depuisLngLat([lng, lat], ordre) {
  if (ordre === ORDRE_LATLNG) return [lat, lng]
  if (ordre === ORDRE_LNGLAT) return [lng, lat]
  throw new TypeError('Ordre des axes non déclaré en sortie (ORDRE_LNGLAT | ORDRE_LATLNG).')
}

/**
 * Repère local d'une toiture. `origine_lnglat` est stocké avec la toiture, tout
 * comme `azimut_deg` : sans eux, des mètres locaux ne veulent plus rien dire.
 */
export function creerRepere({ origine_lnglat, azimut_deg = 0, ordre } = {}) {
  const [lng0, lat0] = versLngLat(origine_lnglat, ordre ?? ORDRE_LNGLAT)
  const a = Number(azimut_deg)
  if (!Number.isFinite(a)) throw new TypeError('`azimut_deg` doit être un nombre.')
  const sin2 = Math.sin(lat0 * RAD) ** 2
  const denom = 1 - E2 * sin2
  return {
    origine_lnglat: [lng0, lat0],
    azimut_deg: a,
    // Rayon de courbure de la première verticale (est-ouest).
    _N: A_WGS84 / Math.sqrt(denom),
    // Rayon de courbure méridien (nord-sud).
    _M: (A_WGS84 * (1 - E2)) / (denom * Math.sqrt(denom)),
    _cosLat0: Math.cos(lat0 * RAD),
  }
}

/**
 * `[lng, lat]` → mètres locaux `{ x, y }`.
 * @param {'lnglat'|'latlng'} [ordre] requis si `point` est un tableau.
 */
export function lngLatVersMetres(repere, point, ordre) {
  const [lng, lat] = versLngLat(point, ordre)
  const [lng0, lat0] = repere.origine_lnglat
  const est = (lng - lng0) * RAD * repere._N * repere._cosLat0
  const nord = (lat - lat0) * RAD * repere._M
  const a = repere.azimut_deg * RAD
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  // +y local = azimut `a` (depuis le Nord, sens horaire) ; +x local = a + 90°.
  return { x: est * cos - nord * sin, y: est * sin + nord * cos }
}

/** Mètres locaux `{ x, y }` → `[lng, lat]` (l'inverse exact du précédent). */
export function metresVersLngLat(repere, { x, y }) {
  const a = repere.azimut_deg * RAD
  const cos = Math.cos(a)
  const sin = Math.sin(a)
  const est = Number(x) * cos + Number(y) * sin
  const nord = -Number(x) * sin + Number(y) * cos
  const [lng0, lat0] = repere.origine_lnglat
  const lat = lat0 + nord / repere._M / RAD
  const lng = lng0 + est / (repere._N * repere._cosLat0) / RAD
  return [lng, lat]
}

/** Contour géographique → `sommets_m`. L'ordre des axes du contour est DÉCLARÉ. */
export function contourVersSommetsM(repere, contour, ordre) {
  if (!Array.isArray(contour)) return []
  return contour.map((p) => lngLatVersMetres(repere, p, ordre))
}

/** `sommets_m` → contour géographique dans l'ordre d'axes DÉCLARÉ en sortie. */
export function sommetsMVersContour(repere, sommetsM, ordre) {
  if (!Array.isArray(sommetsM)) return []
  return sommetsM.map((s) => depuisLngLat(metresVersLngLat(repere, s), ordre))
}

/* ════════════════════════════════════════════════════════════════════════════
   GÉOMÉTRIE PLANE, en mètres locaux — le vocabulaire commun de l'atelier
   (tracé, zones, enveloppes). Tout est exprimé en mètres : aucune de ces
   fonctions ne connaît les pixels ni les degrés.
   ════════════════════════════════════════════════════════════════════════════ */

/** Aire signée (positive = sens trigonométrique). */
export function aireSignee(sommets) {
  if (!Array.isArray(sommets) || sommets.length < 3) return 0
  let s = 0
  for (let i = 0; i < sommets.length; i += 1) {
    const p = sommets[i]
    const q = sommets[(i + 1) % sommets.length]
    s += Number(p.x) * Number(q.y) - Number(q.x) * Number(p.y)
  }
  return s / 2
}

/** Aire en m² (toujours positive). */
export function aireM2(sommets) {
  return Math.abs(aireSignee(sommets))
}

/** Périmètre en m (polygone fermé). */
export function perimetreM(sommets) {
  if (!Array.isArray(sommets) || sommets.length < 2) return 0
  let p = 0
  for (let i = 0; i < sommets.length; i += 1) {
    const a = sommets[i]
    const b = sommets[(i + 1) % sommets.length]
    p += Math.hypot(Number(b.x) - Number(a.x), Number(b.y) - Number(a.y))
  }
  return p
}

function orientation(p, q, r) {
  const v = (q.y - p.y) * (r.x - q.x) - (q.x - p.x) * (r.y - q.y)
  if (Math.abs(v) < 1e-12) return 0
  return v > 0 ? 1 : 2
}

function surSegment(p, q, r) {
  return (
    q.x <= Math.max(p.x, r.x) + 1e-12 &&
    q.x >= Math.min(p.x, r.x) - 1e-12 &&
    q.y <= Math.max(p.y, r.y) + 1e-12 &&
    q.y >= Math.min(p.y, r.y) - 1e-12
  )
}

/** Deux segments [p1,p2] et [p3,p4] se croisent-ils ? (cas colinéaires inclus) */
export function segmentsSeCroisent(p1, p2, p3, p4) {
  const o1 = orientation(p1, p2, p3)
  const o2 = orientation(p1, p2, p4)
  const o3 = orientation(p3, p4, p1)
  const o4 = orientation(p3, p4, p2)
  if (o1 !== o2 && o3 !== o4) return true
  if (o1 === 0 && surSegment(p1, p3, p2)) return true
  if (o2 === 0 && surSegment(p1, p4, p2)) return true
  if (o3 === 0 && surSegment(p3, p1, p4)) return true
  if (o4 === 0 && surSegment(p3, p2, p4)) return true
  return false
}

/**
 * Le contour se recoupe-t-il ? Un polygone auto-intersecté n'a pas d'aire
 * exploitable : le calepinage y poserait des rangées dans le vide. Refusé à la
 * saisie (AOF84), jamais « réparé » en douce.
 */
export function contourSeCroise(sommets) {
  const n = Array.isArray(sommets) ? sommets.length : 0
  if (n < 4) return false
  for (let i = 0; i < n; i += 1) {
    const a1 = sommets[i]
    const a2 = sommets[(i + 1) % n]
    for (let j = i + 1; j < n; j += 1) {
      // On saute les segments adjacents (ils partagent un sommet par construction).
      if (j === i || (j + 1) % n === i || (i + 1) % n === j) continue
      if (segmentsSeCroisent(a1, a2, sommets[j], sommets[(j + 1) % n])) return true
    }
  }
  return false
}

/** Un point est-il dans le polygone ? (lancer de rayon, mètres locaux) */
export function pointDansPolygone(point, sommets) {
  if (!Array.isArray(sommets) || sommets.length < 3) return false
  let dedans = false
  for (let i = 0, j = sommets.length - 1; i < sommets.length; j = i, i += 1) {
    const xi = Number(sommets[i].x)
    const yi = Number(sommets[i].y)
    const xj = Number(sommets[j].x)
    const yj = Number(sommets[j].y)
    const croise = yi > point.y !== yj > point.y
    if (croise && point.x < ((xj - xi) * (point.y - yi)) / (yj - yi) + xi) dedans = !dedans
  }
  return dedans
}
