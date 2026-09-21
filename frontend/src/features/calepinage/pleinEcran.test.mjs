// CALX129 — LE PLEIN ÉCRAN RÉVERSIBLE, LOGIQUE PURE. Exécuté en CI :
//   node --test src/features/calepinage/pleinEcran.test.mjs
//
// Ce fichier prouve que la bascule ne touche jamais l'élément passé (aucun
// démontage possible : ce module ne connaît même pas son contenu), que le
// repli CSS prend le relais quand l'API Fullscreen est absente ou refuse, et
// que la sortie est suivie par l'état RAPPORTÉ par le document (Échap),
// jamais deviné.
import test from 'node:test'
import assert from 'node:assert/strict'

import { basculerPleinEcran, estEnPleinEcranSur } from './pleinEcran.js'

/** Élément DOM factice — piste les appels, jamais un vrai navigateur. */
function elementFactice({ requestFullscreen } = {}) {
  return { requestFullscreen }
}

test('CALX129 — bascule ENTRÉE : API Fullscreen disponible, aucun repli CSS', async () => {
  let appele = false
  const el = elementFactice({ requestFullscreen: async () => { appele = true } })
  const doc = {}
  const r = await basculerPleinEcran(el, doc, false)
  assert.equal(appele, true)
  assert.deepEqual(r, { enPleinEcran: true, repliCss: false })
})

test('CALX129 — bascule ENTRÉE : API Fullscreen absente ⇒ repli CSS, même réversibilité', async () => {
  const el = elementFactice({ requestFullscreen: undefined })
  const r = await basculerPleinEcran(el, {}, false)
  assert.deepEqual(r, { enPleinEcran: true, repliCss: true })
})

test('CALX129 — bascule ENTRÉE : la demande est REFUSÉE par le navigateur ⇒ repli CSS', async () => {
  const el = elementFactice({ requestFullscreen: async () => { throw new Error('refusé') } })
  const r = await basculerPleinEcran(el, {}, false)
  assert.deepEqual(r, { enPleinEcran: true, repliCss: true })
})

test('CALX129 — bascule SORTIE : quitte le plein écran du document quand il porte l’élément', async () => {
  let sortie = false
  const el = elementFactice()
  const doc = { fullscreenElement: el, exitFullscreen: async () => { sortie = true } }
  const r = await basculerPleinEcran(el, doc, true)
  assert.equal(sortie, true)
  assert.deepEqual(r, { enPleinEcran: false, repliCss: false })
})

test('CALX129 — bascule SORTIE : le document ne porte déjà plus l’élément (sorti par Échap) ⇒ état à jour sans re-sortir', async () => {
  let appele = false
  const el = elementFactice()
  const doc = { fullscreenElement: null, exitFullscreen: async () => { appele = true } }
  const r = await basculerPleinEcran(el, doc, true)
  assert.equal(appele, false)
  assert.deepEqual(r, { enPleinEcran: false, repliCss: false })
})

test('CALX129 — élément absent : l’état ne bouge pas (rien à basculer)', async () => {
  const r1 = await basculerPleinEcran(null, {}, false)
  assert.deepEqual(r1, { enPleinEcran: false, repliCss: false })
  const r2 = await basculerPleinEcran(undefined, {}, true)
  assert.deepEqual(r2, { enPleinEcran: true, repliCss: false })
})

test('CALX129 — estEnPleinEcranSur : suit le document, jamais un état deviné', () => {
  const el = elementFactice()
  const autre = elementFactice()
  assert.equal(estEnPleinEcranSur({ fullscreenElement: el }, el), true)
  assert.equal(estEnPleinEcranSur({ fullscreenElement: autre }, el), false)
  assert.equal(estEnPleinEcranSur({ fullscreenElement: null }, el), false)
  assert.equal(estEnPleinEcranSur(null, el), false)
})
