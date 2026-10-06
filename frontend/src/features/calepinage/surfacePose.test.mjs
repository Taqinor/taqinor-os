import test from 'node:test'
import assert from 'node:assert/strict'
import {
  documentSurfacePose, saisieDepuisSurface, reponseDepuisSurface,
  remplacerSurface, retirerSurface, repereLibre, surfacesDuGenre,
  entreeMoteurChangee, nombre, pasMesure, tauxOccupation, contourTerrain,
} from './surfacePose.js'
import { SAISIE_SOL } from '../../test/fixtures/saisiesSurfacePose.js'

/* ACAL25 (C-ACAL-034) — UNE fonction pour Terrain ET Ombrière : module et allée
   persistés puis relus. Test-du-test : retirer `moduleWc` de
   `documentSurfacePose` ⇒ l'aller-retour ombrière ci-dessous rougit. */

const REPONSE = {
  plans: [{
    modules: 24,
    tables: [{ x0: 0, x1: 4, y0: 0, y1: 2 }, { x0: 0, x1: 4, y0: 3, y1: 5 }],
    rangees: [{ y0: 0 }, { y0: 3 }],
  }],
  version_moteur: 'v1',
  hash_entree: 'h-123',
}

const OMBRIERE = {
  repere: 'OMB-1',
  label: 'Ombrière parking',
  buildingId: 'BAT-A',
  largeurM: '30',
  profondeurM: '10',
  clearHeightM: '2.5',
  tiltDeg: '7',
  flowAzimuthDeg: '180',
  moduleLongM: '2.38',
  moduleCourtM: '1.13',
  puissanceWc: '620',
  modulesParTable: '4',
  alleeM: '0',
}

/** ACAL345 — la saisie de référence partagée avec l'écran (`mode_terrain.test.jsx`). */
const SOL = SAISIE_SOL

test('documentSurfacePose(ombrière 620 Wc, allée 0) porte module et allée ; saisieDepuisSurface rend la saisie d’origine', () => {
  const s = documentSurfacePose(OMBRIERE, REPONSE, 'ombriere')
  assert.equal(s.kind, 'ombriere')
  assert.equal(s.moduleWc, 620)
  assert.equal(s.moduleLongM, 2.38)
  assert.equal(s.moduleCourtM, 1.13)
  assert.equal(s.modulesParTable, 4)
  assert.equal(s.alleeM, 0)
  assert.deepEqual(saisieDepuisSurface(s), OMBRIERE)
})

test('le champ au sol suit la même fonction : module et allée, saisie relue à l’identique', () => {
  const s = documentSurfacePose({ ...SOL, alleeM: '1.5' }, REPONSE, 'sol')
  assert.equal(s.kind, 'sol')
  assert.equal(s.terrainSlopeDeg, 3)
  assert.equal(s.moduleWc, 720)
  assert.equal(s.alleeM, 1.5)
  assert.deepEqual(saisieDepuisSurface(s), { ...SOL, alleeM: '1.5' })
})

test('une allée vide est persistée null (jamais 0) et n’est pas relue', () => {
  const s = documentSurfacePose(SOL, REPONSE, 'sol')
  assert.equal(s.alleeM, null)
  assert.equal('alleeM' in saisieDepuisSurface(s), false)
})

test('enregistrer → rouvrir → enregistrer sans toucher : surface octet-identique (module, allée, engine, hashEntree)', () => {
  for (const [saisie, kind] of [[OMBRIERE, 'ombriere'], [SOL, 'sol']]) {
    const premiere = documentSurfacePose(saisie, REPONSE, kind)
    const rouverte = documentSurfacePose(
      { ...saisieDepuisSurface(premiere) }, reponseDepuisSurface(premiere), kind)
    assert.equal(JSON.stringify(rouverte), JSON.stringify(premiere), kind)
    assert.equal(rouverte.engine.hashEntree, 'h-123')
    assert.equal(rouverte.engine.rowPitchM, 3)
  }
})

test('le plan relu n’invente aucune rangée : le pas mesuré revient par _pasRecharge', () => {
  const s = documentSurfacePose(SOL, REPONSE, 'sol')
  const relu = reponseDepuisSurface(s)
  assert.equal(relu._pasRecharge, 3)
  assert.equal(relu.plans[0].rangees, undefined)
})

test('seules les entrées du moteur invalident le plan', () => {
  for (const cle of ['largeurM', 'profondeurM', 'rowAzimuthDeg', 'flowAzimuthDeg', 'tiltDeg',
    'moduleLongM', 'moduleCourtM', 'puissanceWc', 'modulesParTable', 'alleeM']) {
    assert.equal(entreeMoteurChangee(cle), true, cle)
  }
  for (const cle of ['penteTerrainDeg', 'clearHeightM', 'label', 'buildingId', 'repere']) {
    assert.equal(entreeMoteurChangee(cle), false, cle)
  }
})

test('remplacerSurface remplace PAR id (à sa place) et ne touche pas les autres', () => {
  const A = documentSurfacePose({ ...SOL, repere: 'S-A' }, REPONSE, 'sol')
  const B = documentSurfacePose({ ...SOL, repere: 'S-B' }, REPONSE, 'sol')
  const O = documentSurfacePose(OMBRIERE, REPONSE, 'ombriere')
  const B2 = documentSurfacePose({ ...SOL, repere: 'S-B', tiltDeg: '30' }, REPONSE, 'sol')
  const liste = remplacerSurface([A, O, B], B2)
  assert.deepEqual(liste, [A, O, B2])
  const C = documentSurfacePose({ ...SOL, repere: 'S-C' }, REPONSE, 'sol')
  assert.deepEqual(remplacerSurface([A], C), [A, C])
  assert.deepEqual(remplacerSurface(undefined, C), [C])
})

test('retirerSurface retire la surface (genre + id) et rien d’autre', () => {
  const A = documentSurfacePose({ ...SOL, repere: 'S-A' }, REPONSE, 'sol')
  const O = documentSurfacePose({ ...OMBRIERE, repere: 'S-A' }, REPONSE, 'ombriere')
  assert.deepEqual(retirerSurface([A, O], 'sol', 'S-A'), [O])
  assert.deepEqual(retirerSurface([A, O], 'ombriere', 'S-A'), [A])
  assert.deepEqual(retirerSurface(null, 'sol', 'S-A'), [])
})

test('repereLibre propose un repère non pris, par genre', () => {
  const T1 = documentSurfacePose({ ...SOL, repere: 'TERRAIN' }, REPONSE, 'sol')
  const T2 = documentSurfacePose({ ...SOL, repere: 'TERRAIN-2' }, REPONSE, 'sol')
  assert.equal(repereLibre([], 'sol'), 'TERRAIN')
  assert.equal(repereLibre([T1], 'sol'), 'TERRAIN-2')
  assert.equal(repereLibre([T1, T2], 'sol'), 'TERRAIN-3')
  assert.equal(repereLibre([T1], 'ombriere'), 'OMBRIERE')
  assert.equal(surfacesDuGenre([T1, T2], 'ombriere').length, 0)
})

test('les mesures pures restent : nombre, contour, pas, taux', () => {
  assert.equal(nombre(''), null)
  assert.equal(nombre('0'), 0)
  assert.equal(contourTerrain('0', '10'), null)
  assert.equal(pasMesure([{ y0: 0 }]), null)
  assert.equal(tauxOccupation(REPONSE.plans[0].tables, 200), 16 / 200)
})
