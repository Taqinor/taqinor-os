/**
 * CAL96 — géométrie PURE des obstructions PROCHES (CAL94), converties en
 * azimut/hauteur angulaire vues depuis un point de référence, pour les surimprimer
 * sur `SunDiagram.jsx`. MÊME repère que `apps/web/src/lib/horizonEngine.ts`/
 * `shadingEngine.ts` (azimut 0=Nord/90=Est/180=Sud/270=Ouest, ENU mètres, WGS84
 * sphérique) — dupliqué pour la même raison que `horizonMath.js` (pas d'alias
 * `@rooflib` dans `frontend/vitest.config.js`, hors périmètre de cette lane).
 *
 * SOURCES PERSISTÉES SEULEMENT — les ombres tracées à la main (`shadeObstructions`)
 * ne voyagent JAMAIS dans le document (`apps/web/src/scripts/roofPro11/context.ts`,
 * champ `readonly`, session seule) : cet écran, qui ne lit QUE le document
 * (`roof_layout`), ne peut donc surimprimer que les DEUX sources qui, elles, y sont
 * écrites — les obstacles de toiture à hauteur saisie (CAL66) et les objets
 * d'environnement (CAL67). Un obstacle SANS hauteur saisie ne projette aucune ombre
 * (règle du moteur) : il est écarté ici aussi, jamais une hauteur inventée.
 */

const DEG2RAD = Math.PI / 180
const WGS84_RADIUS = 6378137

/** Hypothèse de hauteur de toit PAR DÉFAUT (2 étages × 3 m), affichée comme telle —
 *  même valeur que `apps/web/src/scripts/roofPro11/constants.ts` (FLOORS×FLOOR_HEIGHT_M).
 *  Sert à ramener un objet RÉFÉRENCÉ AU SOL (environnement) à sa hauteur EFFECTIVE
 *  au-dessus du plan du champ. */
export const HAUTEUR_TOIT_HYPOTHESE_M = 6

/** ENU (mètres, est=x/nord=y) d'un point lng/lat relatif à une origine lng/lat. */
function versENU(origineLng, origineLat, lng, lat) {
  const dx = (lng - origineLng) * DEG2RAD * WGS84_RADIUS * Math.cos(origineLat * DEG2RAD)
  const dy = (lat - origineLat) * DEG2RAD * WGS84_RADIUS
  return { dx, dy }
}

/**
 * Azimut (°, 0=Nord/90=Est) et hauteur angulaire (°) d'un point à `hauteurEffectiveM`
 * au-dessus du plan du champ, vu depuis l'origine. `null` si le point est confondu
 * avec l'origine (azimut indéfini) — jamais un azimut à 0° inventé.
 */
export function azimutHauteur(origineLng, origineLat, cibleLng, cibleLat, hauteurEffectiveM) {
  if (![origineLng, origineLat, cibleLng, cibleLat, hauteurEffectiveM].every(Number.isFinite)) return null
  const { dx, dy } = versENU(origineLng, origineLat, cibleLng, cibleLat)
  const distanceM = Math.hypot(dx, dy)
  if (distanceM < 0.5) return null
  const azimuthDeg = ((Math.atan2(dx, dy) / DEG2RAD) + 360) % 360
  const elevationDeg = Math.atan2(hauteurEffectiveM, distanceM) / DEG2RAD
  return { azimuthDeg, elevationDeg, distanceM }
}

const LIBELLE_TYPE_OBSTACLE = {
  cheminee: 'Cheminée', ventilation: 'VMC', chien_assis: 'Chien-assis',
  edicule: 'Édicule', antenne: 'Antenne', autre: 'Obstacle',
}

/**
 * Les obstacles de TOITURE (CAL66) d'UNE zone, convertis en azimut/hauteur angulaire
 * vus depuis `origine` (le point de référence de la zone — son centroïde). Un obstacle
 * SANS hauteur saisie (`heightM`) est écarté : il ne projette aucune ombre, donc rien à
 * surimprimer (même règle que le moteur d'ombrage proche). La hauteur d'un obstacle de
 * toiture est prise TELLE QUELLE (déjà au-dessus du plan du champ).
 */
export function obstructionsDesObstacles(origine, obstacles) {
  if (!origine || !Number.isFinite(origine.lng) || !Number.isFinite(origine.lat)) return []
  return (Array.isArray(obstacles) ? obstacles : [])
    .filter((o) => typeof o?.heightM === 'number' && o.heightM > 0)
    .map((o) => {
      const pos = azimutHauteur(origine.lng, origine.lat, o.centerLng, o.centerLat, o.heightM)
      if (!pos) return null
      return { ...pos, label: LIBELLE_TYPE_OBSTACLE[o.type] ?? 'Obstacle' }
    })
    .filter(Boolean)
}

/**
 * Les objets d'ENVIRONNEMENT (CAL67, arbres/bâtiments voisins) convertis en
 * azimut/hauteur angulaire, RÉFÉRENCÉS AU SOL : leur hauteur EFFECTIVE au-dessus du
 * plan du champ est `heightM − roofHeightM` (jamais négative — un objet plus bas que
 * le toit ne masque rien). Un objet sans hauteur saisie est écarté.
 */
export function obstructionsDeLEnvironnement(origine, environment, roofHeightM = HAUTEUR_TOIT_HYPOTHESE_M) {
  if (!origine || !Number.isFinite(origine.lng) || !Number.isFinite(origine.lat)) return []
  return (Array.isArray(environment) ? environment : [])
    .filter((o) => typeof o?.heightM === 'number' && o.heightM > 0)
    .map((o) => {
      const effectif = Math.max(0, o.heightM - roofHeightM)
      if (effectif <= 0) return null
      const pos = azimutHauteur(origine.lng, origine.lat, o.centerLng, o.centerLat, effectif)
      if (!pos) return null
      return { ...pos, label: o.label || (o.kind === 'arbre' ? 'Arbre' : 'Bâtiment') }
    })
    .filter(Boolean)
}

/** Les DEUX sources réunies pour UNE zone (obstacles + environnement) — ordre stable :
 *  obstacles de toiture d'abord, puis environnement. */
export function obstructionsDuPan(origine, obstacles, environment, roofHeightM = HAUTEUR_TOIT_HYPOTHESE_M) {
  return [
    ...obstructionsDesObstacles(origine, obstacles),
    ...obstructionsDeLEnvironnement(origine, environment, roofHeightM),
  ]
}

/** Centroïde {lng,lat} d'un contour [[lng,lat],…], ou null si < 1 sommet. */
export function centroideDuContour(vertices) {
  if (!Array.isArray(vertices) || !vertices.length) return null
  let lng = 0
  let lat = 0
  for (const v of vertices) {
    lng += v[0]
    lat += v[1]
  }
  return { lng: lng / vertices.length, lat: lat / vertices.length }
}
