// EZ8 — tests de la file BINAIRE (photos) de l'outbox terrain.
// Run: node --test src/features/installations/offline/binaryOutbox.test.mjs
//
// Scénario du plan : coupure réseau pendant 3 photos → 0 perdue, badge exact,
// synchro au retour, quota dépassé = message clair, purge au logout.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  BinaryOutbox, OutboxQuotaError, memoryStore, BINARY_MAX_OPS,
} from './outbox.js'

const buf = (n = 8) => new ArrayBuffer(n)

// Erreur RÉSEAU = pas de `response` (convention axios) ; erreur SERVEUR = avec.
const erreurReseau = () => Object.assign(new Error('offline'), { response: undefined })
const erreurServeur = (detail) => Object.assign(new Error('400'), {
  response: { data: { detail } },
})

test('une photo filée porte sa clé d’idempotence, sa taille et son horodatage', async () => {
  const ob = new BinaryOutbox({ uploader: async () => ({}) })
  const id = await ob.enqueue('intervention.photo', { intervention: 1, slot: 'avant' },
    { bytes: buf(1234), name: 'toit.jpg', type: 'image/jpeg' })
  const [op] = await ob.pending()
  assert.ok(id && op.client_op_id === id)
  assert.equal(op.size, 1234)
  assert.equal(op.meta.intervention, 1)
  assert.ok(op.queuedAt)
  assert.equal(await ob.bytes(), 1234)
})

test('refuse une charge qui n’est pas un ArrayBuffer (jamais un Blob)', async () => {
  const ob = new BinaryOutbox({ uploader: async () => ({}) })
  await assert.rejects(
    () => ob.enqueue('intervention.photo', {}, { bytes: 'pas-un-buffer' }),
    /ArrayBuffer/)
})

test('coupure réseau pendant 3 photos → 0 perdue, badge exact, synchro au retour', async () => {
  const envoyees = []
  let reseau = false
  const ob = new BinaryOutbox({
    store: memoryStore(),
    uploader: async (op) => {
      if (!reseau) throw erreurReseau()
      envoyees.push(op.client_op_id)
      return {}
    },
  })
  for (const slot of ['avant', 'pendant', 'apres']) {
    await ob.enqueue('intervention.photo', { intervention: 7, slot }, { bytes: buf(100) })
  }
  assert.equal(await ob.count(), 3, 'les 3 photos sont en file (badge)')

  // Toujours hors ligne : le flush ne perd RIEN.
  let res = await ob.flush()
  assert.equal(res.flushed, 0)
  assert.equal(await ob.count(), 3)

  // Réseau revenu : tout part.
  reseau = true
  res = await ob.flush()
  assert.equal(res.flushed, 3)
  assert.equal(res.remaining, 0)
  assert.equal(envoyees.length, 3)
  assert.equal(await ob.count(), 0)
})

test('un refus SERVEUR garde la photo en file, marquée (jamais un effacement silencieux)', async () => {
  const ob = new BinaryOutbox({
    uploader: async () => { throw erreurServeur('Créneau inconnu.') },
  })
  await ob.enqueue('intervention.photo', { intervention: 1, slot: 'x' }, { bytes: buf() })
  const res = await ob.flush()
  assert.equal(res.failed, 1)
  assert.equal(await ob.count(), 1)
  const [op] = await ob.failed()
  assert.equal(op.serverError, 'Créneau inconnu.')
  assert.equal(op.attempts, 1)
  // Seul un abandon EXPLICITE la retire.
  await ob.discard(op.client_op_id)
  assert.equal(await ob.count(), 0)
})

test('la file s’arrête à la première coupure et garde l’ordre', async () => {
  let ok = 1
  const ob = new BinaryOutbox({
    uploader: async () => {
      if (ok-- <= 0) throw erreurReseau()
      return {}
    },
  })
  await ob.enqueue('intervention.photo', { slot: 'a' }, { bytes: buf() })
  await ob.enqueue('intervention.photo', { slot: 'b' }, { bytes: buf() })
  await ob.enqueue('intervention.photo', { slot: 'c' }, { bytes: buf() })
  const res = await ob.flush()
  assert.equal(res.flushed, 1)
  assert.equal(res.remaining, 2)
  const restantes = await ob.pending()
  assert.deepEqual(restantes.map((o) => o.meta.slot), ['b', 'c'])
})

test('plafond du NOMBRE de photos : message clair, jamais un échec muet', async () => {
  const ob = new BinaryOutbox({ uploader: async () => ({}), maxOps: 2 })
  await ob.enqueue('intervention.photo', {}, { bytes: buf() })
  await ob.enqueue('intervention.photo', {}, { bytes: buf() })
  await assert.rejects(
    () => ob.enqueue('intervention.photo', {}, { bytes: buf() }),
    (e) => e instanceof OutboxQuotaError && /File d’envoi pleine/.test(e.message))
  assert.equal(await ob.count(), 2)
  assert.ok(BINARY_MAX_OPS > 0)
})

test('plafond de TAILLE : message clair', async () => {
  const ob = new BinaryOutbox({ uploader: async () => ({}), maxBytes: 1000 })
  await ob.enqueue('intervention.photo', {}, { bytes: buf(900) })
  await assert.rejects(
    () => ob.enqueue('intervention.photo', {}, { bytes: buf(200) }),
    (e) => e.quota === true)
})

test('la file survit au rechargement (même store) et se purge au logout', async () => {
  const store = memoryStore()
  const ob = new BinaryOutbox({ store, uploader: async () => ({}) })
  await ob.enqueue('intervention.photo', { intervention: 3 }, { bytes: buf(10) })
  // Nouvelle instance sur le MÊME store = ce que fait un rechargement d'onglet.
  const apresRechargement = new BinaryOutbox({ store, uploader: async () => ({}) })
  assert.equal(await apresRechargement.count(), 1)
  // Purge (déconnexion sur terminal partagé — patron LW45).
  await apresRechargement.clear()
  assert.equal(await apresRechargement.count(), 0)
  assert.equal(await new BinaryOutbox({ store, uploader: async () => ({}) }).count(), 0)
})

test('un flush concurrent est ignoré (pas de double envoi)', async () => {
  let enCours = 0
  let maxParallele = 0
  const ob = new BinaryOutbox({
    uploader: async () => {
      enCours += 1
      maxParallele = Math.max(maxParallele, enCours)
      await new Promise((r) => setTimeout(r, 5))
      enCours -= 1
      return {}
    },
  })
  await ob.enqueue('intervention.photo', {}, { bytes: buf() })
  await ob.enqueue('intervention.photo', {}, { bytes: buf() })
  const [a, b] = await Promise.all([ob.flush(), ob.flush()])
  assert.ok(a.skipped || b.skipped, 'un des deux flush doit être ignoré')
  assert.equal(maxParallele, 1)
  assert.equal(await ob.count(), 0)
})
