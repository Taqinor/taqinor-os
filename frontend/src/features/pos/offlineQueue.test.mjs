// NTRET1 — tests de la logique PURE de la file de synchronisation caisse
// hors-ligne. Run with: node --test src/features/pos/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  OfflineVenteQueue, memoryStore, makeUuidClient, estHorsLigne, BACKOFF_STEPS_MS,
} from './offlineQueue.js'

// Serveur factice : dédupe par uuid_client (même contrat que le backend réel
// — apps/pos/views.py::VenteComptoirViewSet.perform_create) : rejouer un
// uuid_client déjà vu renvoie la vente existante au lieu d'en créer une 2e.
function fakeServer() {
  const created = new Map() // uuid_client -> vente
  let nextId = 1
  const calls = []
  const sender = async (payload) => {
    calls.push(payload)
    if (payload.uuid_client && created.has(payload.uuid_client)) {
      return created.get(payload.uuid_client)
    }
    const vente = { id: nextId++, uuid_client: payload.uuid_client || null }
    if (payload.uuid_client) created.set(payload.uuid_client, vente)
    return vente
  }
  return { sender, created, calls }
}

test('makeUuidClient génère des identifiants uniques non vides', () => {
  const a = makeUuidClient()
  const b = makeUuidClient()
  assert.ok(a && b && a !== b)
})

test('enqueue met en file, persiste via le store, et attribue un uuid_client', async () => {
  const store = memoryStore()
  const q = new OfflineVenteQueue({ store, sender: async () => ({ id: 1 }) })
  const uuid = await q.enqueue({ client: 7 })
  assert.ok(uuid)
  assert.equal(await q.count(), 1)
  const [op] = await q.pending()
  assert.equal(op.payload.uuid_client, uuid)
  assert.equal(op.payload.client, 7)

  // Une nouvelle instance branchée sur le même store retrouve la file.
  const q2 = new OfflineVenteQueue({ store, sender: async () => ({ id: 1 }) })
  assert.equal(await q2.count(), 1)
})

test('flush vide la file quand le serveur confirme la vente', async () => {
  const { sender } = fakeServer()
  const q = new OfflineVenteQueue({ store: memoryStore(), sender })
  await q.enqueue({ client: 1 })
  await q.enqueue({ client: 2 })
  const res = await q.flush()
  assert.equal(res.flushed, 2)
  assert.equal(res.remaining, 0)
  assert.equal(await q.count(), 0)
})

test('échec RÉSEAU du sender : la file reste INTACTE (rien perdu)', async () => {
  let calls = 0
  const sender = async () => { calls += 1; throw new Error('network down') }
  const q = new OfflineVenteQueue({ store: memoryStore(), sender })
  await q.enqueue({ client: 1 })
  const res = await q.flush()
  assert.equal(res.flushed, 0)
  assert.equal(await q.count(), 1)
  assert.equal(calls, 1)
})

test('un rejeu en double (même uuid_client) est un no-op sûr, pas un doublon', async () => {
  const server = fakeServer()
  const store = memoryStore()
  const q = new OfflineVenteQueue({ store, sender: server.sender })
  const uuid = await q.enqueue({ client: 1 })
  await q.flush()
  assert.equal(await q.count(), 0)

  // On re-file EXACTEMENT le même uuid_client (simule une file rejouée deux
  // fois, ex. après un crash de l'onglet) — le serveur voit un uuid déjà
  // connu et ne crée jamais de 2e vente.
  await q.enqueue({ client: 1 }, { uuidClient: uuid })
  await q.flush()
  assert.equal(server.created.size, 1)
  assert.equal(server.calls.filter((p) => p.uuid_client === uuid).length, 2)
})

test('refus SERVEUR (pas réseau) : op gardée, marquée serverError, jamais perdue en silence', async () => {
  const err = new Error('rejected')
  err.response = { data: { detail: 'Client inconnu.' } }
  const sender = async () => { throw err }
  const q = new OfflineVenteQueue({ store: memoryStore(), sender })
  await q.enqueue({ client: 999 })
  const res = await q.flush()
  assert.equal(res.flushed, 0)
  assert.equal(await q.count(), 1)
  const failed = await q.failed()
  assert.equal(failed.length, 1)
  assert.equal(failed[0].serverError, 'Client inconnu.')
})

test('backoff : une op rejetée n’est PAS retentée avant son délai', async () => {
  let calls = 0
  const sender = async () => { calls += 1; throw new Error('down') }
  const q = new OfflineVenteQueue({ store: memoryStore(), sender })
  await q.enqueue({ client: 1 })
  const t0 = 1_000_000
  await q.flush({ now: t0 })
  assert.equal(calls, 1)
  // Retenter immédiatement (avant le premier palier de backoff) est sauté.
  await q.flush({ now: t0 + 1 })
  assert.equal(calls, 1)
  // Une fois le premier palier écoulé, le prochain flush retente bien.
  await q.flush({ now: t0 + BACKOFF_STEPS_MS[0] + 1 })
  assert.equal(calls, 2)
})

test('discard retire explicitement une op en erreur (jamais un effet du flush)', async () => {
  const err = new Error('rejected')
  err.response = { data: { detail: 'Refusé.' } }
  const sender = async () => { throw err }
  const q = new OfflineVenteQueue({ store: memoryStore(), sender })
  const uuid = await q.enqueue({ client: 1 })
  await q.flush()
  assert.equal(await q.count(), 1)
  await q.discard(uuid)
  assert.equal(await q.count(), 0)
})

test('estHorsLigne : navigator.onLine=false détecte hors-ligne sans sonde', async () => {
  // `navigator` global Node n'a qu'un getter (pas de setter) : une simple
  // affectation lève en mode strict (modules ESM). On le redéfinit
  // temporairement via defineProperty, puis on restaure le descripteur
  // d'origine — jamais de fuite entre tests.
  const original = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  Object.defineProperty(globalThis, 'navigator', {
    value: { onLine: false }, configurable: true, writable: true,
  })
  try {
    assert.equal(await estHorsLigne(), true)
  } finally {
    if (original) Object.defineProperty(globalThis, 'navigator', original)
  }
})

test('estHorsLigne : sonde ping en échec confirme la perte réseau', async () => {
  const failingPing = async () => { throw new Error('unreachable') }
  assert.equal(await estHorsLigne({ ping: failingPing }), true)
})

test('estHorsLigne : sonde ping réussie confirme la connexion', async () => {
  const okPing = async () => 'pong'
  assert.equal(await estHorsLigne({ ping: okPing }), false)
})
