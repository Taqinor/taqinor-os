// CALX121 — LA COUPE TRANSVERSALE, LOGIQUE PURE. Exécuté en CI :
//   vitest (porté de node:test par ACAL254 — import @rooflib)
//
// Ce fichier prouve que le pas inter-rangées est bien MESURÉ sur les panneaux
// déjà posés (jamais une seconde formule), que la longueur d'ombre dessinée
// suit celle qu'implique la géométrie posée (même astronomie que le builder,
// dérivée ici via la MÊME fonction `sunPosition` que la production — jamais
// une valeur de repère tapée à la main), et que chaque géométrie manquante
// rend un état « non calculée » explicite, jamais un dessin inventé.
import { test } from 'vitest'
import assert from 'node:assert/strict'

import { construireCoupe, pasRangeeMesure } from './coupeRangees.js'
import { FRONT_STRUT_M as MONTANT_AVANT_M } from '@rooflib/roofPro2'
import { rowPitchM, sunPositionWinterSolstice, DESIGN_SOLAR_HOUR } from '@rooflib/estimatorBrainV2'

const DEG2RAD = Math.PI / 180

/** Un module du catalogue `modules[]` du document (cotes de la fiche produit). */
const MODULES = [{
  id: 'm1', produitId: 1, libelle: 'Module d’essai 550 Wc', longueurMm: 2279, largeurMm: 1134,
  epaisseurMm: 30, poidsKg: 28, pmaxWc: 550, source: 'fiche produit',
}]
const PROFONDEUR_MODULE_M = 1.134

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

test('CALX121 — construireCoupe : l’ombre dessinée retombe sur le pas du moteur V2 (même astronomie)', () => {
  const tiltDeg = 13
  const latitudeDeg = 33.5
  const tiltRad = tiltDeg * DEG2RAD
  const riseM = PROFONDEUR_MODULE_M * Math.sin(tiltRad)
  const depthFootprintM = PROFONDEUR_MODULE_M * Math.cos(tiltRad)
  const elevDeg = sunPositionWinterSolstice(latitudeDeg, DESIGN_SOLAR_HOUR).elevationDeg
  // Le pas du moteur V2 = empreinte + ombre + marge ; la marge est lue SUR le
  // moteur (pas à plat), jamais retapée.
  const pitch = rowPitchM(PROFONDEUR_MODULE_M, tiltDeg, latitudeDeg)
  const marge = rowPitchM(PROFONDEUR_MODULE_M, 0, latitudeDeg) - PROFONDEUR_MODULE_M

  const panels = [...rangee(0), ...rangee(-pitch)]
  const r = construireCoupe({
    zone: { geometry: { moduleId: 'm1', tiltDeg, flush: false, azimuthDeg: 180, panels } },
    latitudeDeg,
    modules: MODULES,
  })

  assert.equal(r.disponible, true)
  // `pasRangeeMesure` arrondit au millimètre (bruit flottant du placement) :
  // la tolérance suit cette résolution, jamais l'exactitude bit à bit.
  assert.ok(Math.abs(r.rowPitchM - pitch) < 2e-3)
  assert.ok(Math.abs(r.profondeurModuleM - PROFONDEUR_MODULE_M) < 1e-9)
  assert.ok(Math.abs(r.depthFootprintM - depthFootprintM) < 1e-9)
  assert.ok(Math.abs(r.riseM - riseM) < 1e-9)
  assert.ok(Math.abs(r.hauteurHorsToutM - (MONTANT_AVANT_M + riseM)) < 1e-9)
  assert.ok(Math.abs(r.rayonSolaireDeg - elevDeg) < 1e-9)
  assert.equal(r.heureConceptionH, DESIGN_SOLAR_HOUR)
  // L'ombre dessinée + l'empreinte + la marge du moteur redonnent SON pas.
  assert.ok(Math.abs(r.longueurOmbreM + depthFootprintM + marge - pitch) < 1e-9)
})

test('CALX121 — construireCoupe : pose affleurante ⇒ rangées jointives, aucune hauteur hors-tout ni ombre', () => {
  const tiltDeg = 20
  const tiltRad = tiltDeg * DEG2RAD
  const depthFootprintM = PROFONDEUR_MODULE_M * Math.cos(tiltRad)
  const panels = [...rangee(0), ...rangee(-depthFootprintM)]

  const r = construireCoupe({
    zone: { geometry: { moduleId: 'm1', tiltDeg, flush: true, azimuthDeg: 180, panels } },
    latitudeDeg: 33.5,
    modules: MODULES,
  })

  assert.equal(r.disponible, true)
  assert.equal(r.flush, true)
  assert.equal(r.hauteurHorsToutM, null)
  assert.equal(r.longueurOmbreM, 0)
  assert.ok(Math.abs(r.rowPitchM - depthFootprintM) < 2e-3)
})
