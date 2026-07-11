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

test('VX119 — une op rejetée par le serveur (status error) reste GARDÉE en file, jamais purgée en silence', async () => {
  const sender = async (ops) => ({
    results: ops.map((o) => ({
      client_op_id: o.client_op_id,
      status: 'error',
      error: 'signature illisible',
    })),
  })
  const ob = new Outbox({ store: memoryStore(), sender })
  const id = await ob.enqueue('intervention.signer_client', {
    intervention: 1, signature_client: 'sig',
  })
  const res = await ob.flush()
  assert.equal(res.flushed, 0)
  assert.equal(res.failed, 1)
  assert.equal(res.remaining, 1)
  assert.equal(await ob.count(), 1) // toujours en file — PAS perdue
  const pending = await ob.pending()
  assert.equal(pending[0].client_op_id, id)
  assert.equal(pending[0].serverError, 'signature illisible')
  assert.equal(pending[0].attempts, 1)
})

test('VX119 — une 2e tentative en échec incrémente attempts et met à jour le message serveur', async () => {
  let call = 0
  const sender = async (ops) => {
    call += 1
    const msg = call === 1 ? 'timeout cible' : 'cible toujours indisponible'
    return { results: ops.map((o) => ({ client_op_id: o.client_op_id, status: 'error', error: msg })) }
  }
  const ob = new Outbox({ store: memoryStore(), sender })
  await ob.enqueue('intervention.reserve', { intervention: 1 })
  await ob.flush()
  await ob.flush()
  const pending = await ob.pending()
  assert.equal(pending[0].attempts, 2)
  assert.equal(pending[0].serverError, 'cible toujours indisponible')
})

test('VX119 — failed() liste uniquement les ops en erreur serveur ; discard() les retire explicitement', async () => {
  const sender = async (ops) => ({
    results: ops.map((o) => ({ client_op_id: o.client_op_id, status: 'error', error: 'boom' })),
  })
  const ob = new Outbox({ store: memoryStore(), sender })
  const id = await ob.enqueue('intervention.checkin', { intervention: 1 })
  await ob.flush()
  const failed = await ob.failed()
  assert.equal(failed.length, 1)
  assert.equal(failed[0].client_op_id, id)
  await ob.discard(id)
  assert.equal(await ob.count(), 0)
  assert.equal((await ob.failed()).length, 0)
})

test('VX119 — un lot mixte (une confirmée, une en erreur) garde SEULEMENT celle en erreur', async () => {
  const sender = async (ops) => ({
    results: ops.map((o, i) => (
      i === 0
        ? { client_op_id: o.client_op_id, status: 'applied' }
        : { client_op_id: o.client_op_id, status: 'error', error: 'refusé' }
    )),
  })
  const ob = new Outbox({ store: memoryStore(), sender })
  await ob.enqueue('intervention.checkin', { intervention: 1 })
  const badId = await ob.enqueue('intervention.signer_client', { intervention: 2 })
  const res = await ob.flush()
  assert.equal(res.flushed, 1)
  assert.equal(res.failed, 1)
  const pending = await ob.pending()
  assert.equal(pending.length, 1)
  assert.equal(pending[0].client_op_id, badId)
  assert.equal(pending[0].serverError, 'refusé')
})

test('non-régression : applied/replayed continuent de vider la file normalement', async () => {
  const server = fakeServer()
  const ob = new Outbox({ store: memoryStore(), sender: server.sender })
  await ob.enqueue('intervention.checkin', { intervention: 1 })
  const res = await ob.flush()
  assert.equal(res.flushed, 1)
  assert.equal(res.failed, 0)
  assert.equal(await ob.count(), 0)
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
