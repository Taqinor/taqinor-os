import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  calibrer,
  estCalibree,
  peutTracer,
  peutCoter,
  libelleEchelle,
  verifierVraisemblance,
  pxVersM,
  mVersPx,
  reechelonner,
  ECART_PX_MINIMAL,
} from './calibration.js'

/* AOF80 — les deux cas exigés par le « Done = » :
   1. impossible de créer une cote sur un underlay NON calibré ;
   2. alerte quand l'échelle obtenue est aberrante. */

test('sans calibration, tracé et cotation sont BLOQUÉS et l’état dit « échelle inconnue »', () => {
  assert.equal(estCalibree(null), false)
  assert.equal(peutTracer(null), false)
  assert.equal(peutCoter(null), false)
  assert.equal(libelleEchelle(null), 'échelle inconnue')
  // Une calibration refusée n'ouvre rien non plus.
  const refusee = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 0, y: 0 }, distanceReelleM: 10 })
  assert.equal(refusee.valide, false)
  assert.equal(peutCoter(refusee), false)
})

test('deux points + une distance réelle donnent le facteur px→m et débloquent les outils', () => {
  const cal = calibrer({ p1: { x: 100, y: 100 }, p2: { x: 600, y: 100 }, distanceReelleM: 25 })
  assert.equal(cal.valide, true)
  assert.equal(cal.distancePx, 500)
  assert.equal(cal.metresParPixel, 0.05)
  assert.equal(peutTracer(cal), true)
  assert.equal(peutCoter(cal), true)
  assert.match(libelleEchelle(cal), /1 m = 20\.0 px/)
})

test('la distance px est euclidienne (points en diagonale)', () => {
  const cal = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 300, y: 400 }, distanceReelleM: 50 })
  assert.equal(cal.distancePx, 500)
  assert.equal(cal.metresParPixel, 0.1)
})

test('une distance réelle absurde ou absente est refusée avec un motif FR', () => {
  const a = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 0 })
  assert.equal(a.valide, false)
  assert.match(a.motif, /distance réelle/i)
  const b = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 'x' })
  assert.equal(b.valide, false)
})

test('deux points trop proches sont refusés (l’erreur de clic contaminerait tout le plan)', () => {
  const cal = calibrer({
    p1: { x: 0, y: 0 },
    p2: { x: ECART_PX_MINIMAL - 4, y: 0 },
    distanceReelleM: 10,
  })
  assert.equal(cal.valide, false)
  assert.match(cal.motif, /trop proches/)
})

test('ALERTE quand l’échelle est aberrante — distance saisie en centimètres', () => {
  // 2562 cm saisis comme « 2562 m » sur 500 px → 5,12 m par pixel : aberrant.
  const trop = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 2562 })
  assert.equal(trop.valide, true)
  const v1 = verifierVraisemblance(trop)
  assert.equal(v1.niveau, 'alerte')
  assert.match(v1.message, /suspecte/i)

  // 25,62 m saisis en millimètres (25620) sur 5 000 000 px n'arrive pas ; le cas
  // symétrique est un plan démesurément grand pour une distance minuscule.
  const petit = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 100000, y: 0 }, distanceReelleM: 25 })
  const v2 = verifierVraisemblance(petit)
  assert.equal(v2.niveau, 'alerte')

  // Le cas normal ne déclenche AUCUNE alerte.
  const bon = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 25.62 })
  assert.equal(verifierVraisemblance(bon).niveau, 'ok')
})

test('les conversions px↔m refusent de répondre sans calibration', () => {
  assert.equal(pxVersM(null, 100), null)
  assert.equal(mVersPx(null, 10), null)
  const cal = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 25 })
  assert.equal(pxVersM(cal, 100), 5)
  assert.equal(mVersPx(cal, 5), 100)
})

test('recalibrer ne perd pas le tracé : le ré-échelonnage est calculable et explicite', () => {
  const ancienne = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 25 })
  const nouvelle = calibrer({ p1: { x: 0, y: 0 }, p2: { x: 500, y: 0 }, distanceReelleM: 50 })
  const sommets = [
    { x: 0, y: 0 },
    { x: 25, y: 0 },
    { x: 25, y: 10 },
  ]
  const rescale = reechelonner(sommets, ancienne, nouvelle)
  assert.deepEqual(rescale.map((s) => s.x), [0, 50, 50])
  assert.deepEqual(rescale.map((s) => s.y), [0, 0, 20])
  // Les sommets d'origine ne sont pas mutés : rien n'est appliqué en douce.
  assert.deepEqual(sommets.map((s) => s.x), [0, 25, 25])
})
