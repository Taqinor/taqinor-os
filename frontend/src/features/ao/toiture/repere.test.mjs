import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ORDRE_LNGLAT,
  ORDRE_LATLNG,
  versLngLat,
  depuisLngLat,
  creerRepere,
  lngLatVersMetres,
  metresVersLngLat,
  contourVersSommetsM,
  sommetsMVersContour,
  aireM2,
  perimetreM,
  contourSeCroise,
  segmentsSeCroisent,
  pointDansPolygone,
} from './repere.js'

/* AOF83 — le contrat des axes, testé DANS LES DEUX SENS et sur un cas marocain
   réel : la toiture de Casablanca, 25,62 m × 51,10 m (relevé FRDISI). */

// Casablanca — origine du repère local.
const ORIGINE = [-7.6328, 33.5883] // [lng, lat] — l'ordre est DANS le nom.

test('une paire nue sans ordre déclaré est REFUSÉE', () => {
  assert.throws(() => versLngLat([-7.6328, 33.5883]), /Ordre des axes non déclaré/)
})

test('les deux ordres déclarés désignent le MÊME point', () => {
  const a = versLngLat([-7.6328, 33.5883], ORDRE_LNGLAT)
  const b = versLngLat([33.5883, -7.6328], ORDRE_LATLNG)
  assert.deepEqual(a, b)
  assert.deepEqual(a, [-7.6328, 33.5883])
})

test('un objet nommé { lng, lat } n’a pas besoin d’ordre', () => {
  assert.deepEqual(versLngLat({ lng: -7.6328, lat: 33.5883 }), [-7.6328, 33.5883])
  assert.deepEqual(versLngLat({ longitude: -7.6, latitude: 33.5 }), [-7.6, 33.5])
})

test('un ordre déclaré à l’envers est détecté par le domaine de la latitude', () => {
  // Le contour du lead CRM est en [lat, lng] : le lire comme du [lng, lat]
  // donnerait une « latitude » de -7,63 — plausible ! Le cas franchement
  // impossible (lat > 90) doit lever ; c'est pourquoi l'ordre reste DÉCLARÉ et
  // n'est jamais deviné.
  assert.throws(() => versLngLat([33.5883, 120], ORDRE_LNGLAT), /Latitude hors domaine/)
})

test('la sortie aussi déclare son ordre', () => {
  assert.deepEqual(depuisLngLat([-7.6328, 33.5883], ORDRE_LATLNG), [33.5883, -7.6328])
  assert.deepEqual(depuisLngLat([-7.6328, 33.5883], ORDRE_LNGLAT), [-7.6328, 33.5883])
  assert.throws(() => depuisLngLat([-7.6328, 33.5883]), /non déclaré/)
})

test('aller-retour lng/lat → mètres → lng/lat sous le CENTIMÈTRE (cas marocain)', () => {
  const repere = creerRepere({ origine_lnglat: ORIGINE, azimut_deg: 0 })
  // Quatre points autour de l'origine, à l'échelle d'une toiture réelle.
  const points = [
    [-7.6328, 33.5883],
    [-7.63225, 33.5883], // ~51 m à l'est
    [-7.63225, 33.58853], // ~25 m au nord
    [-7.6335, 33.5878],
  ]
  for (const p of points) {
    const m = lngLatVersMetres(repere, p, ORDRE_LNGLAT)
    const retour = metresVersLngLat(repere, m)
    // Erreur convertie en mètres pour être lisible : < 1 cm.
    const dLng = (retour[0] - p[0]) * 111320 * Math.cos(p[1] * (Math.PI / 180))
    const dLat = (retour[1] - p[1]) * 110574
    assert.ok(Math.hypot(dLng, dLat) < 0.01, `écart aller-retour ${Math.hypot(dLng, dLat)} m`)
  }
})

test('l’aller-retour tient aussi avec un azimut non nul (toiture non orientée nord)', () => {
  const repere = creerRepere({ origine_lnglat: ORIGINE, azimut_deg: 37.5 })
  const p = [-7.63225, 33.58853]
  const retour = metresVersLngLat(repere, lngLatVersMetres(repere, p, ORDRE_LNGLAT))
  const dLng = (retour[0] - p[0]) * 111320 * Math.cos(p[1] * (Math.PI / 180))
  const dLat = (retour[1] - p[1]) * 110574
  assert.ok(Math.hypot(dLng, dLat) < 0.01)
})

test('à azimut nul, +x va à l’EST et +y au NORD', () => {
  const repere = creerRepere({ origine_lnglat: ORIGINE })
  const est = lngLatVersMetres(repere, [-7.6318, 33.5883], ORDRE_LNGLAT)
  assert.ok(est.x > 0, 'un point plus à l’est doit avoir x > 0')
  assert.ok(Math.abs(est.y) < 1e-6)
  const nord = lngLatVersMetres(repere, [-7.6328, 33.5893], ORDRE_LNGLAT)
  assert.ok(nord.y > 0, 'un point plus au nord doit avoir y > 0')
  assert.ok(Math.abs(nord.x) < 1e-6)
})

test('un contour du CRM ([lat, lng]) et le même du tool ([lng, lat]) donnent les MÊMES mètres', () => {
  const repere = creerRepere({ origine_lnglat: ORIGINE })
  const contourTool = [
    [-7.6328, 33.5883],
    [-7.63225, 33.5883],
    [-7.63225, 33.58853],
  ]
  const contourCrm = contourTool.map(([lng, lat]) => [lat, lng])
  const a = contourVersSommetsM(repere, contourTool, ORDRE_LNGLAT)
  const b = contourVersSommetsM(repere, contourCrm, ORDRE_LATLNG)
  assert.equal(a.length, 3)
  a.forEach((p, i) => {
    assert.ok(Math.abs(p.x - b[i].x) < 1e-9)
    assert.ok(Math.abs(p.y - b[i].y) < 1e-9)
  })
})

test('sommets_m → contour rend l’ordre demandé, et seulement lui', () => {
  const repere = creerRepere({ origine_lnglat: ORIGINE })
  const sommets = [{ x: 0, y: 0 }, { x: 25.62, y: 0 }]
  const enLatLng = sommetsMVersContour(repere, sommets, ORDRE_LATLNG)
  assert.ok(Math.abs(enLatLng[0][0] - 33.5883) < 1e-9, 'première composante = latitude')
  assert.throws(() => sommetsMVersContour(repere, sommets, undefined), /non déclaré/)
})

test('un rectangle de 25,62 × 51,10 rend bien son aire et son périmètre', () => {
  const rect = [
    { x: 0, y: 0 },
    { x: 25.62, y: 0 },
    { x: 25.62, y: 51.1 },
    { x: 0, y: 51.1 },
  ]
  assert.ok(Math.abs(aireM2(rect) - 25.62 * 51.1) < 1e-9)
  assert.ok(Math.abs(perimetreM(rect) - 2 * (25.62 + 51.1)) < 1e-9)
})

test('l’auto-intersection est détectée (contour en nœud papillon)', () => {
  const propre = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 10, y: 10 },
    { x: 0, y: 10 },
  ]
  const croise = [
    { x: 0, y: 0 },
    { x: 10, y: 0 },
    { x: 0, y: 10 },
    { x: 10, y: 10 },
  ]
  assert.equal(contourSeCroise(propre), false)
  assert.equal(contourSeCroise(croise), true)
  assert.equal(
    segmentsSeCroisent({ x: 0, y: 0 }, { x: 10, y: 10 }, { x: 0, y: 10 }, { x: 10, y: 0 }),
    true,
  )
})

test('un « L » d’un seul tenant n’est PAS auto-intersecté', () => {
  const enL = [
    { x: 0, y: 0 },
    { x: 30, y: 0 },
    { x: 30, y: 12 },
    { x: 12, y: 12 },
    { x: 12, y: 40 },
    { x: 0, y: 40 },
  ]
  assert.equal(contourSeCroise(enL), false)
  assert.ok(Math.abs(aireM2(enL) - (30 * 12 + 12 * 28)) < 1e-9)
  assert.equal(pointDansPolygone({ x: 5, y: 35 }, enL), true)
  assert.equal(pointDansPolygone({ x: 25, y: 35 }, enL), false)
})
