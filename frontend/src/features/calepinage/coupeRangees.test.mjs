// CALX121 — LA COUPE TRANSVERSALE, LOGIQUE PURE. Exécuté en CI :
//   node --test src/features/calepinage/coupeRangees.test.mjs
//
// Ce fichier prouve que le pas inter-rangées est bien MESURÉ sur les panneaux
// déjà posés (jamais une seconde formule), que la longueur d'ombre dessinée
// suit celle qu'implique la géométrie posée (même astronomie que le builder,
// dérivée ici via la MÊME fonction `sunPosition` que la production — jamais
// une valeur de repère tapée à la main), et que chaque géométrie manquante
// rend un état « non calculée » explicite, jamais un dessin inventé.
import test from 'node:test'
import assert from 'node:assert/strict'

import { construireCoupe, pasRangeeMesure, PROFONDEUR_MODULE_M, MONTANT_AVANT_M } from './coupeRangees.js'
import { sunPosition, JOUR_SOLSTICE_HIVER } from './horizonMath.js'

const DEG2RAD = Math.PI / 180

/** Trois panneaux d'une même rangée (même projection), à `cy` fixe. */
function rangee(cy, xs = [-1, 0, 1]) {
  return xs.map((cx) => ({ cx, cy }))
}

test('CALX121 — pasRangeeMesure lit le plus petit écart entre rangées distinctes (azimut sud)', () => {
  const panels = [...rangee(0), ...rangee(-2.5), ...rangee(-5)]
  // azimut 180 (sud) : la projection sur l'axe d'empilement vaut -cy.
  assert.equal(pasRangeeMesure(panels, 180), 2.5)
})

test('CALX121 — pasRangeeMesure fonctionne pour un azimut quelconque (est)', () => {
  const panels = [
    { cx: 1, cy: -1 }, { cx: 1, cy: 1 },
    { cx: 3.2, cy: -1 }, { cx: 3.2, cy: 1 },
  ]
  // azimut 90 (est) : la projection vaut cx.
  assert.equal(pasRangeeMesure(panels, 90), Math.round((3.2 - 1) * 1000) / 1000)
})

test('CALX121 — pasRangeeMesure : moins de deux rangées distinctes ⇒ non mesurable', () => {
  assert.equal(pasRangeeMesure(rangee(0), 180), null)
  assert.equal(pasRangeeMesure([], 180), null)
  assert.equal(pasRangeeMesure(rangee(0), NaN), null)
})

test('CALX121 — construireCoupe : aucune géométrie posée ⇒ non calculée, motif nommé', () => {
  const r = construireCoupe({ zone: { id: 'p1' }, latitudeDeg: 33.5 })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /aucune géométrie posée/)
})

test('CALX121 — construireCoupe : inclinaison absente du document ⇒ non calculée', () => {
  const r = construireCoupe({
    zone: { geometry: { azimuthDeg: 180, panels: [...rangee(0), ...rangee(-2)] } },
    latitudeDeg: 33.5,
  })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /inclinaison/)
})

test('CALX121 — construireCoupe : une seule rangée posée ⇒ pas non mesurable, non calculée', () => {
  const r = construireCoupe({
    zone: { geometry: { tiltDeg: 13, azimuthDeg: 180, panels: rangee(0) } },
    latitudeDeg: 33.5,
  })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /Moins de deux rangées/)
})

test('CALX121 — construireCoupe : latitude du site inconnue ⇒ non calculée', () => {
  const r = construireCoupe({
    zone: { geometry: { tiltDeg: 13, azimuthDeg: 180, panels: [...rangee(0), ...rangee(-2)] } },
    latitudeDeg: null,
  })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /Latitude/)
})

test('CALX121 — construireCoupe : la longueur d’ombre dessinée suit celle du builder (même astronomie)', () => {
  const tiltDeg = 13
  const latitudeDeg = 33.5
  const tiltRad = tiltDeg * DEG2RAD
  const riseM = PROFONDEUR_MODULE_M * Math.sin(tiltRad)
  const depthFootprintM = PROFONDEUR_MODULE_M * Math.cos(tiltRad)
  const elevDeg = sunPosition(latitudeDeg, JOUR_SOLSTICE_HIVER, 12).elevationDeg
  const shadowLenAttendue = riseM / Math.tan(elevDeg * DEG2RAD)
  const pitch = depthFootprintM + shadowLenAttendue

  const panels = [...rangee(0), ...rangee(-pitch)]
  const r = construireCoupe({
    zone: { geometry: { tiltDeg, flush: false, azimuthDeg: 180, panels } },
    latitudeDeg,
  })

  assert.equal(r.disponible, true)
  // `pasRangeeMesure` arrondit au millimètre (bruit flottant du placement) :
  // la tolérance suit cette résolution, jamais l'exactitude bit à bit.
  assert.ok(Math.abs(r.rowPitchM - pitch) < 2e-3)
  assert.ok(Math.abs(r.depthFootprintM - depthFootprintM) < 1e-9)
  assert.ok(Math.abs(r.hauteurHorsToutM - (MONTANT_AVANT_M + riseM)) < 1e-9)
  assert.ok(Math.abs(r.rayonSolaireDeg - elevDeg) < 1e-9)
  // La longueur d'ombre RENVOYÉE, dérivée de la géométrie posée (tiltDeg +
  // latitude), retombe sur celle qui a produit le pas mesuré : rien n'a été
  // recalculé « à côté » de ce que le pas raconte déjà.
  assert.ok(Math.abs(r.longueurOmbreM - shadowLenAttendue) < 2e-3)
})

test('CALX121 — construireCoupe : pose affleurante ⇒ rangées jointives, aucune hauteur hors-tout ni ombre', () => {
  const tiltDeg = 20
  const tiltRad = tiltDeg * DEG2RAD
  const depthFootprintM = PROFONDEUR_MODULE_M * Math.cos(tiltRad)
  const panels = [...rangee(0), ...rangee(-depthFootprintM)]

  const r = construireCoupe({
    zone: { geometry: { tiltDeg, flush: true, azimuthDeg: 180, panels } },
    latitudeDeg: 33.5,
  })

  assert.equal(r.disponible, true)
  assert.equal(r.flush, true)
  assert.equal(r.hauteurHorsToutM, null)
  assert.equal(r.longueurOmbreM, 0)
  assert.ok(Math.abs(r.rowPitchM - depthFootprintM) < 2e-3)
})
