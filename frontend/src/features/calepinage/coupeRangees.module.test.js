// ACAL255 — la coupe des rangées est dessinée au module RÉEL du pan et au soleil de
// dimensionnement (10 h solaire, solstice d'hiver), jamais au module 720 Wc supposé
// ni au soleil de midi. Exécuté par vitest (alias @rooflib / @roofpro).
import { test } from 'vitest'
import assert from 'node:assert/strict'

import { construireCoupe, MOTIF_MODULE_NON_RENSEIGNE } from './coupeRangees.js'

const DEG2RAD = Math.PI / 180
const LATITUDE = 33.57
const INCLINAISON = 13

/** Un module du catalogue `modules[]` : petit côté 1,134 m (cotes de la fiche). */
const MODULE_550 = {
  id: 'm550', produitId: 7, libelle: 'Module 550 Wc', longueurMm: 2279, largeurMm: 1134,
  epaisseurMm: 30, poidsKg: 28, pmaxWc: 550, source: 'fiche produit',
}

const rangee = (cy) => [-1, 0, 1].map((cx) => ({ cx, cy }))
const zone = (extra = {}) => ({
  geometry: {
    tiltDeg: INCLINAISON, flush: false, azimuthDeg: 180,
    panels: [...rangee(0), ...rangee(-3)], ...extra,
  },
})

test('ACAL255 — coupe au module du pan et au soleil de 10 h', () => {
  const r = construireCoupe({
    zone: zone({ moduleId: 'm550' }), latitudeDeg: LATITUDE, modules: [MODULE_550],
  })
  assert.equal(r.disponible, true)
  // Montée = petit côté du module du pan × sin 13°.
  assert.ok(Math.abs(r.riseM - 1.134 * Math.sin(INCLINAISON * DEG2RAD)) < 1e-9)
  // Soleil de 10 h au solstice d'hiver : ≈ 26,2° (et non 32,99° à midi).
  assert.ok(Math.abs(r.rayonSolaireDeg - 26.2) < 0.1, `rayon ${r.rayonSolaireDeg}`)
  assert.equal(r.heureConceptionH, 10)
  // Ombre portée du module 1,134 m à 10 h (rise 0,255 m × |cos γ| / tan 26,2°).
  const attendue = (1.134 * Math.sin(INCLINAISON * DEG2RAD) * 0.8596) / Math.tan(26.25 * DEG2RAD)
  assert.ok(Math.abs(r.longueurOmbreM - attendue) < 0.01, `ombre ${r.longueurOmbreM}`)
  // Plus longue que celle de midi (même module) : le soleil de 10 h est plus bas.
  const midi = (1.134 * Math.sin(INCLINAISON * DEG2RAD)) / Math.tan(32.99 * DEG2RAD)
  assert.ok(r.longueurOmbreM > midi)
})

test('ACAL255 — le module d’un autre pan ne change pas ce pan (cotes par moduleId)', () => {
  const grand = { ...MODULE_550, id: 'grand', longueurMm: 2384, largeurMm: 1303 }
  const r = construireCoupe({
    zone: zone({ moduleId: 'grand' }), latitudeDeg: LATITUDE, modules: [MODULE_550, grand],
  })
  assert.ok(Math.abs(r.profondeurModuleM - 1.303) < 1e-9)
})

test('ACAL255 — sans module désigné : « module non renseigné », jamais 1,303 m supposé', () => {
  const r = construireCoupe({ zone: zone(), latitudeDeg: LATITUDE, modules: [MODULE_550] })
  assert.equal(r.disponible, false)
  assert.equal(r.motif, MOTIF_MODULE_NON_RENSEIGNE)
  assert.match(r.motif, /Module non renseigné/)
})

test('ACAL255 — module désigné mais sans cotes : refus nommant le champ, pas de coupe', () => {
  const sansCotes = { ...MODULE_550, longueurMm: null }
  const r = construireCoupe({
    zone: zone({ moduleId: 'm550' }), latitudeDeg: LATITUDE, modules: [sansCotes],
  })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /longueur/)
})

test('ACAL255 — moduleId absent du catalogue : refus, pas de repli muet', () => {
  const r = construireCoupe({
    zone: zone({ moduleId: 'inconnu' }), latitudeDeg: LATITUDE, modules: [MODULE_550],
  })
  assert.equal(r.disponible, false)
  assert.match(r.motif, /inconnu/)
})
