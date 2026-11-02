// ACHT69 — Outbox.flush distingue une erreur RÉSEAU (aucune réponse : file intacte)
// d'une RÉPONSE HTTP du serveur (403/400/500 : ops du lot marquées `serverError`,
// comptées dans failed(), abandonnables), comme BinaryOutbox.
// Run: node --test src/lib/offlineOutbox.erreurHttp.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { Outbox, memoryStore } from './offlineOutbox.js'

const DETAIL = 'Vous n’avez pas la permission d’effectuer cette action.'
const erreurHttp = (status, detail = DETAIL) => Object.assign(new Error(`HTTP ${status}`), {
  response: { status, data: detail ? { detail } : {} },
})
const reseau = () => Object.assign(new Error('Network Error'), { code: 'ERR_NETWORK' })

async function fileDeuxOps(sender, store = memoryStore()) {
  const ob = new Outbox({ store, sender })
  await ob.enqueue('t.op', { n: 1 }, { clientOpId: 'a' })
  await ob.enqueue('t.op', { n: 2 }, { clientOpId: 'b' })
  return { ob, store }
}

test('erreur réseau : file intacte, rien de marqué', async () => {
  const { ob } = await fileDeuxOps(async () => { throw reseau() })
  for (let i = 0; i < 2; i += 1) {
    assert.deepEqual(await ob.flush(), { skipped: false, flushed: 0, failed: 0, remaining: 2 })
  }
  assert.equal((await ob.failed()).length, 0)
  assert.ok((await ob.pending()).every((op) => op.serverError === undefined))
})

for (const statut of [403, 400]) {
  test(`réponse HTTP ${statut} : tout le lot en échec visible et abandonnable`, async () => {
    const { ob, store } = await fileDeuxOps(async () => { throw erreurHttp(statut) })
    const flush1 = await ob.flush()
    const flush2 = await ob.flush()
    assert.equal(flush1.failed, 2, 'flush1 compte les 2 ops en échec')
    assert.equal(flush2.flushed, 0)
    const echecs = await ob.failed()
    assert.equal(echecs.length, 2)
    assert.ok(echecs.every((op) => op.serverError === DETAIL), 'la raison du serveur est portée par chaque op')
    assert.ok((await ob.pending()).every((op) => !!op.serverError), 'aucune op en attente silencieuse')

    // Persistance : recharger la file depuis son stockage garde l'état d'échec.
    const rechargee = new Outbox({ store })
    assert.equal((await rechargee.failed()).length, 2)

    // Abandon explicite possible.
    await ob.discard('a')
    assert.equal((await ob.failed()).length, 1)
  })
}

// ACHT128 — 500 et 502/503/504 sont réessayés (échecs comptés dans `attempts`), puis marqués
// `serverError` au 3e échec : visibles et abandonnables.
for (const [statut, detail, attendu] of [
  [500, 'Erreur interne.', 'Erreur interne.'],
  [503, null, 'Serveur indisponible (HTTP 503) : réessayez plus tard ou abandonnez l\'envoi.'],
]) {
  test(`${statut} persistant : réessayé deux fois, marqué au 3e flush`, async () => {
    const { ob, store } = await fileDeuxOps(async () => { throw erreurHttp(statut, detail) })
    for (const essai of [1, 2]) {
      const res = await ob.flush()
      assert.equal(res.failed, 0, `flush ${essai} : rien en échec`)
      const ops = await ob.pending()
      assert.ok(ops.every((op) => op.serverError === undefined && op.attempts === essai))
    }
    const res3 = await ob.flush()
    assert.equal(res3.failed, 2)
    const echecs = await ob.failed()
    assert.equal(echecs.length, 2)
    assert.ok(echecs.every((op) => op.serverError === attendu && op.attempts === 3))
    // Persistance : recharger la file relit `attempts` et `serverError` identiques.
    const rechargee = new Outbox({ store })
    assert.deepEqual((await rechargee.failed()).map((op) => [op.attempts, op.serverError]),
      [[3, attendu], [3, attendu]])
    await ob.discard('a')
    assert.equal((await ob.failed()).length, 1, 'abandonnable')
  })
}

test('403 marqué au premier essai ; réseau jamais marqué ni compté (inchangé)', async () => {
  const a = await fileDeuxOps(async () => { throw erreurHttp(403) })
  assert.equal((await a.ob.flush()).failed, 2)
  const b = await fileDeuxOps(async () => { throw reseau() })
  await b.ob.flush()
  assert.ok((await b.ob.pending()).every((op) => op.attempts === undefined && !op.serverError))
})

test('un 503 transitoire puis une op qui passe : retirée normalement', async () => {
  let n = 0
  const { ob } = await fileDeuxOps(async (ops) => {
    n += 1
    if (n === 1) throw erreurHttp(503)
    return { results: ops.map((o) => ({ client_op_id: o.client_op_id, status: 'applied' })) }
  })
  assert.equal((await ob.flush()).failed, 0)
  const res = await ob.flush()
  assert.equal(res.flushed, 2)
  assert.equal(res.remaining, 0)
})

test('une nouvelle op part normalement après un échec HTTP', async () => {
  let mode = 'refus'
  const envoyes = []
  const sender = async (ops) => {
    if (mode === 'refus') throw erreurHttp(403)
    envoyes.push(ops.map((o) => o.client_op_id))
    return { results: ops.map((o) => ({ client_op_id: o.client_op_id, status: 'applied' })) }
  }
  const { ob } = await fileDeuxOps(sender)
  await ob.flush()
  mode = 'ok'
  await ob.enqueue('t.op', { n: 3 }, { clientOpId: 'c' })
  const res = await ob.flush()
  assert.equal(res.flushed, 1)
  assert.deepEqual(envoyes, [['c']], 'seules les ops non refusées partent')
  assert.equal((await ob.failed()).length, 2, 'les refusées restent visibles jusqu’à l’abandon')
})
