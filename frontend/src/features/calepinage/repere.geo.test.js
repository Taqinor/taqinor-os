// ACAL281 — repere.js mesure sur la MÊME sphère (R = 6 378 137 m) que le serveur
// (core/calepinage/geo.py), l'atelier et apps/web (roof.ts). Avant : rayons de
// courbure de l'ellipsoïde ⇒ 276,82 m² pour un rectangle que le serveur mesure
// 278,77 m². Exécuté par vitest.
import { test } from 'vitest'
import assert from 'node:assert/strict'
import {
  ORDRE_LNGLAT,
  RAYON_TERRE_M,
  aireM2,
  contourVersSommetsM,
  creerRepere,
  lngLatVersMetres,
  metresVersLngLat,
} from './repere.js'

const LAT0 = 33.5731
const LNG0 = -7.5898
const DLAT = 0.00015
const DLNG = 0.00018
const CONTOUR = [
  [LNG0, LAT0],
  [LNG0 + DLNG, LAT0],
  [LNG0 + DLNG, LAT0 + DLAT],
  [LNG0, LAT0 + DLAT],
]

// Oracle INDÉPENDANT : la sphère écrite en clair.
const M_PAR_DEG = (Math.PI / 180) * 6378137
const AIRE_SPHERE = DLNG * M_PAR_DEG * Math.cos((LAT0 * Math.PI) / 180) * DLAT * M_PAR_DEG

test('la constante est celle du serveur', () => {
  assert.equal(RAYON_TERRE_M, 6378137)
})

test('même aire que le serveur (sphère), à 0,01 m² près', () => {
  const repere = creerRepere({ origine_lnglat: CONTOUR[0], ordre: ORDRE_LNGLAT })
  const aire = aireM2(contourVersSommetsM(repere, CONTOUR, ORDRE_LNGLAT))
  assert.ok(Math.abs(aire - AIRE_SPHERE) < 0.01, `aire=${aire} attendu=${AIRE_SPHERE}`)
  assert.ok(Math.abs(aire - 278.77) < 0.01, `aire=${aire}`)
})

test("l'aire ne dépend pas de l'azimut du repère", () => {
  const repere = creerRepere({ origine_lnglat: CONTOUR[0], azimut_deg: 37, ordre: ORDRE_LNGLAT })
  const aire = aireM2(contourVersSommetsM(repere, CONTOUR, ORDRE_LNGLAT))
  assert.ok(Math.abs(aire - AIRE_SPHERE) < 0.01, `aire=${aire}`)
})

test('un millième de degré de latitude = 111,32 m (sphère, pas 110,54)', () => {
  const repere = creerRepere({ origine_lnglat: [LNG0, LAT0], ordre: ORDRE_LNGLAT })
  const { y } = lngLatVersMetres(repere, [LNG0, LAT0 + 0.001], ORDRE_LNGLAT)
  assert.ok(Math.abs(y - 0.001 * M_PAR_DEG) < 1e-6, `y=${y}`)
})

test("l'aller-retour reste l'inverse exact", () => {
  const repere = creerRepere({ origine_lnglat: [LNG0, LAT0], azimut_deg: 20, ordre: ORDRE_LNGLAT })
  const point = [LNG0 + DLNG, LAT0 + DLAT]
  const [lng, lat] = metresVersLngLat(repere, lngLatVersMetres(repere, point, ORDRE_LNGLAT))
  assert.ok(Math.abs(lng - point[0]) < 1e-12)
  assert.ok(Math.abs(lat - point[1]) < 1e-12)
})
