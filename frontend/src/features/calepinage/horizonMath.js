/**
 * CAL93/CAL96 — astronomie + horizon, en JS PUR, partagée par `HorizonPanel.jsx`
 * (l'horizon en fond de la course du soleil) et `CourseSoleil.jsx` (le diagramme par
 * pan). ZÉRO React, ZÉRO réseau.
 *
 * POURQUOI UNE COPIE, PAS UN IMPORT DE `apps/web/src/lib` — `frontend/vite.config.js`
 * déclare bien l'alias `@rooflib` vers `apps/web/src/lib` (déjà utilisé à l'exécution
 * par `RepriseCarte.jsx` via `@roofpro/captureBoot`), mais `frontend/vitest.config.js`
 * NE LE DÉCLARE PAS (son commentaire dit pourquoi : la config de test n'embarque pas le
 * plugin de transpilation TS du builder) — un import statique planterait la RÉSOLUTION
 * du module sous Vitest, pas seulement son exécution. Cette lane ne possède pas
 * `frontend/vitest.config.js` (hors périmètre) : on duplique donc la trigonométrie,
 * volontairement PETITE (une fonction de position solaire, une interpolation
 * d'horizon), testée ici et croisée avec `apps/web/tests/horizonEngine.test.ts` (MÊME
 * formule, MÊMES valeurs de repère — solstices/équinoxe).
 *
 * `sunPosition` est l'EXACTE formule de `apps/web/src/lib/roofPro2.ts sunDirection`
 * (même déclinaison, même angle horaire, même convention d'azimut 0=Nord/90=Est).
 */

const DEG2RAD = Math.PI / 180

/** Jours de l'année de repère (mêmes valeurs que `roofPro2.ts`/`shadingEngine.ts`). */
export const JOUR_EQUINOXE = 80
export const JOUR_SOLSTICE_ETE = 172
export const JOUR_SOLSTICE_HIVER = 355

/**
 * Position du soleil (azimut 0=Nord/90=Est/180=Sud/270=Ouest, élévation °, négative
 * sous l'horizon = nuit) — MÊME formule que `roofPro2.ts sunDirection`.
 */
export function sunPosition(latDeg, dayOfYear, hour) {
  const lat = latDeg * DEG2RAD
  const decl = -23.44 * Math.cos((2 * Math.PI * (dayOfYear + 10)) / 365) * DEG2RAD
  const hourAngle = (hour - 12) * 15 * DEG2RAD
  const sinElev = Math.sin(lat) * Math.sin(decl) + Math.cos(lat) * Math.cos(decl) * Math.cos(hourAngle)
  const elev = Math.asin(Math.max(-1, Math.min(1, sinElev)))
  const cosAz = (Math.sin(decl) - Math.sin(elev) * Math.sin(lat)) / (Math.cos(elev) * Math.cos(lat) || 1e-9)
  let az = Math.acos(Math.max(-1, Math.min(1, cosAz)))
  if (hourAngle > 0) az = 2 * Math.PI - az
  return { elevationDeg: elev / DEG2RAD, azimuthDeg: (az / DEG2RAD + 360) % 360 }
}

/** La course du soleil d'un JOUR donné, échantillonnée toutes les `stepH` heures,
 *  NE GARDANT que les points AU-DESSUS de l'horizon (élévation > 0 — la nuit n'a pas de
 *  trace). */
export function sunPathForDay(latDeg, dayOfYear, stepH = 0.25) {
  const points = []
  for (let h = 0; h <= 24; h += stepH) {
    const p = sunPosition(latDeg, dayOfYear, h)
    if (p.elevationDeg > 0) points.push({ ...p, hour: h })
  }
  return points
}

/** Normalise un azimut dans [0, 360). */
function normAz(azimuthDeg) {
  return ((azimuthDeg % 360) + 360) % 360
}

/** Les points d'un profil d'horizon, TRIÉS par azimut, points non finis écartés — ne
 *  MUTE jamais l'entrée. */
export function sortedHorizonPoints(points) {
  return (Array.isArray(points) ? points : [])
    .filter((p) => Number.isFinite(p?.azimuthDeg) && Number.isFinite(p?.heightDeg))
    .map((p) => ({ azimuthDeg: normAz(p.azimuthDeg), heightDeg: p.heightDeg }))
    .sort((a, b) => a.azimuthDeg - b.azimuthDeg)
}

/**
 * Hauteur d'horizon (°) à un azimut donné, interpolée LINÉAIREMENT entre les deux points
 * encadrants (circulaire : le dernier boucle sur le premier). Moins de deux points
 * exploitables → `null` (aucun horizon plat inventé) — MÊME discipline que
 * `apps/web/src/lib/horizonEngine.ts horizonHeightAtAzimuth`.
 */
export function horizonHeightAtAzimuth(points, azimuthDeg) {
  const sorted = sortedHorizonPoints(points)
  if (sorted.length < 2) return sorted.length === 1 ? sorted[0].heightDeg : null
  const az = normAz(azimuthDeg)
  for (let i = 0; i < sorted.length; i++) {
    const a = sorted[i]
    const b = sorted[(i + 1) % sorted.length]
    const azA = a.azimuthDeg
    const azB = i === sorted.length - 1 ? b.azimuthDeg + 360 : b.azimuthDeg
    const azTest = az < azA ? az + 360 : az
    if (azTest >= azA && azTest <= azB) {
      const span = azB - azA
      if (span <= 0) return a.heightDeg
      const t = (azTest - azA) / span
      return a.heightDeg + t * (b.heightDeg - a.heightDeg)
    }
  }
  return sorted[0].heightDeg
}

/** La hauteur maximale RÉELLE du profil, ou `null` si aucun point exploitable — jamais
 *  recalculée ailleurs « à la main ». */
export function horizonMaxHeightDeg(points) {
  const sorted = sortedHorizonPoints(points)
  if (!sorted.length) return null
  return sorted.reduce((max, p) => Math.max(max, p.heightDeg), -Infinity)
}

/**
 * Estimation, pour L'ÉCRAN uniquement (jamais la source de vérité de la production —
 * celle-ci vit dans `apps/web/src/lib/horizonEngine.ts`, appliquée par l'atelier), du
 * nombre d'heures de jour MASQUÉES par l'horizon sur les TROIS jours de repère
 * (solstices + équinoxe), à azimut/élévation échantillonnés toutes les 30 min. Moins de
 * deux points exploitables → 0 (rien à afficher, jamais un chiffre inventé).
 */
export function heuresMasqueesEstimation(latDeg, points) {
  const sorted = sortedHorizonPoints(points)
  if (sorted.length < 2) return 0
  let n = 0
  for (const jour of [JOUR_EQUINOXE, JOUR_SOLSTICE_ETE, JOUR_SOLSTICE_HIVER]) {
    for (let h = 0; h < 24; h += 0.5) {
      const sun = sunPosition(latDeg, jour, h)
      if (sun.elevationDeg <= 0) continue
      const horizon = horizonHeightAtAzimuth(sorted, sun.azimuthDeg)
      if (horizon != null && sun.elevationDeg < horizon) n++
    }
  }
  return n
}
