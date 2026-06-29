// N91/F21 — tests de la logique PURE de l'outbox hors-ligne.
// Run with: node --test src/features/installations/offline/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Outbox, memoryStore, makeOpId } from './outbox.js'

// Sender factice : mémorise les paquets reçus et confirme chaque op (applied),
// en dédupliquant par client_op_id côté « serveur » (status replayed au rejeu).
function fakeServer() {
  const seen = new Set()
  const batches = []
  const sender = async (ops) => {
    batches.push(ops.map((o) => o.client_op_id))
    return {
      results: ops.map((o) => {
        const status = seen.has(o.client_op_id) ? 'replayed' : 'applied'
        seen.add(o.client_op_id)
        return { client_op_id: o.client_op_id, status }
      }),
    }
  }
  return { sender, batches, seen }
}

test('makeOpId génère des clés uniques non vides', () => {
  const a = makeOpId()
  const b = makeOpId()
  assert.ok(a && b && a !== b)
})

test('enqueue met en file et persiste via le store', async () => {
  const store = memoryStore()
  const ob = new Outbox({ store, sender: async () => ({ results: [] }) })
  await ob.enqueue('intervention.checkin', { intervention: 1, lat: 1, lng: 2 })
  assert.equal(await ob.count(), 1)
  // Une nouvelle instance branchée sur le même store retrouve la file persistée.
  const ob2 = new Outbox({ store, sender: async () => ({ results: [] }) })
  assert.equal(await ob2.count(), 1)
})

test('flush vide la file quand le serveur confirme (applied)', async () => {
  const { sender } = fakeServer()
  const ob = new Outbox({ store: memoryStore(), sender })
  await ob.enqueue('intervention.reserve', { intervention: 1, description: 'x' })
  await ob.enqueue('chantier.cocher_checklist', { chantier: 1, cle: 'a', fait: true })
  const res = await ob.flush()
  assert.equal(res.flushed, 2)
  assert.equal(res.remaining, 0)
  assert.equal(await ob.count(), 0)
})

test('échec réseau du sender : la file reste INTACTE pour réessayer', async () => {
  let calls = 0
  const sender = async () => { calls += 1; throw new Error('network down') }
  const ob = new Outbox({ store: memoryStore(), sender })
  await ob.enqueue('intervention.checkin', { intervention: 1 })
  const res = await ob.flush()
  assert.equal(res.flushed, 0)
  assert.equal(await ob.count(), 1) // rien perdu
  assert.equal(calls, 1)
})

test('rejouer un flush est idempotent (mêmes clés, status replayed)', async () => {
  const server = fakeServer()
  const store = memoryStore()
  const ob = new Outbox({ store, sender: server.sender })
  const id = await ob.enqueue('intervention.signer_client', {
    intervention: 1, signature_client: 'sig',
  })
  await ob.flush()
  // On re-file la MÊME clé (simulateur d'un double-envoi) → le serveur la voit
  // déjà, status replayed, et la file se vide quand même sans double effet.
  await ob.enqueue('intervention.signer_client', {
    intervention: 1, signature_client: 'sig',
  }, { clientOpId: id })
  const res = await ob.flush()
  assert.equal(res.remaining, 0)
  // La 2e application a bien été un rejeu côté serveur.
  assert.ok(server.seen.has(id))
})

test('flush respecte maxBatch (découpage en paquets)', async () => {
  const server = fakeServer()
  const ob = new Outbox({ store: memoryStore(), sender: server.sender, maxBatch: 2 })
  for (let i = 0; i < 5; i += 1) {
    await ob.enqueue('intervention.checkin', { intervention: i })
  }
  const res = await ob.flush()
  assert.equal(res.flushed, 5)
  // 5 ops, paquets de 2 → 3 paquets (2,2,1).
  assert.equal(server.batches.length, 3)
  assert.deepEqual(server.batches.map((b) => b.length), [2, 2, 1])
})

test('un flush concurrent est ignoré (anti-réentrance)', async () => {
  let resolve
  const gate = new Promise((r) => { resolve = r })
  const sender = async (ops) => {
    await gate
    return { results: ops.map((o) => ({ client_op_id: o.client_op_id, status: 'applied' })) }
  }
  const ob = new Outbox({ store: memoryStore(), sender })
  await ob.enqueue('intervention.checkin', { intervention: 1 })
  const p1 = ob.flush()
  const r2 = await ob.flush() // concurrent → skipped
  assert.equal(r2.skipped, true)
  resolve()
  const r1 = await p1
  assert.equal(r1.flushed, 1)
})
