// NTMOB28 — pré-chargement matinal de la tournée (décision + remplissage).
import { test, beforeEach } from 'node:test'
import assert from 'node:assert/strict'
import {
  doitPrecharger, prechargerTournee, HEURE_LIMITE,
} from './prechargeMatinale.js'
import { createReadCache, memoryStore } from './readCache.js'

const JOUR = '2026-08-13'

// `marquerPrecharge` écrit dans localStorage : absent sous node:test, les
// accès sont défensifs (le module ne doit jamais lever pour autant).
beforeEach(() => { globalThis.window = undefined })

test('NTMOB28: précharge le matin, en ligne, une seule fois par jour', () => {
  assert.equal(doitPrecharger({
    enLigne: true, heure: 7, jour: JOUR, dejaFait: null }), true)
  // Déjà fait aujourd'hui.
  assert.equal(doitPrecharger({
    enLigne: true, heure: 7, jour: JOUR, dejaFait: JOUR }), false)
  // Fait hier : on repréchage.
  assert.equal(doitPrecharger({
    enLigne: true, heure: 7, jour: JOUR, dejaFait: '2026-08-12' }), true)
})

test('NTMOB28: no-op hors-ligne et hors créneau matinal', () => {
  assert.equal(doitPrecharger({
    enLigne: false, heure: 7, jour: JOUR, dejaFait: null }), false)
  assert.equal(doitPrecharger({
    enLigne: true, heure: HEURE_LIMITE, jour: JOUR, dejaFait: null }), false)
  assert.equal(doitPrecharger({
    enLigne: true, heure: 18, jour: JOUR, dejaFait: null }), false)
})

test('NTMOB28: met en cache la tournée ET chaque intervention du jour', async () => {
  const cache = createReadCache({ store: memoryStore() })
  const stops = [{ id: 1 }, { id: 2 }, { id: 3 }, { id: 4 }, { id: 5 }]
  const n = await prechargerTournee({
    chargerTournee: async () => ({ data: { stops } }),
    cache,
    jour: JOUR,
  })
  assert.equal(n, 5)
  assert.deepEqual((await cache.get('tournee', JOUR)).data, stops)
  assert.deepEqual((await cache.get('intervention', 3)).data, { id: 3 })
})

test('NTMOB28: une panne réseau ne fait jamais échouer le démarrage', async () => {
  const cache = createReadCache({ store: memoryStore() })
  const n = await prechargerTournee({
    chargerTournee: async () => { throw new Error('réseau') },
    cache,
    jour: JOUR,
  })
  assert.equal(n, 0)
  assert.equal(await cache.get('tournee', JOUR), null)
})
