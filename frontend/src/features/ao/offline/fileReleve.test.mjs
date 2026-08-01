// AOF191 — tests de la logique PURE de la file hors-ligne de relevé AO.
// Run with: node --test src/features/ao/offline/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { FileReleve, memoryStore, makeOpId, OP_TYPES_AUTORISES } from './fileReleve.js'

// Sender factice : dédup par client_op_id côté « serveur » (replayed au rejeu),
// et peut être configuré pour renvoyer une erreur ou un conflit sur un id donné.
function fakeServer({ erreurPour, conflitPour } = {}) {
  const seen = new Set()
  const sender = async (ops) => ({
    results: ops.map((o) => {
      if (conflitPour && conflitPour.has(o.client_op_id)) {
        return { client_op_id: o.client_op_id, status: 'conflict', conflict: 'Valeur modifiée ailleurs.' }
      }
      if (erreurPour && erreurPour.has(o.client_op_id)) {
        return { client_op_id: o.client_op_id, status: 'error', error: 'Rejetée.' }
      }
      const status = seen.has(o.client_op_id) ? 'replayed' : 'applied'
      seen.add(o.client_op_id)
      return { client_op_id: o.client_op_id, status }
    }),
  })
  return { sender, seen }
}

test('makeOpId génère des clés uniques non vides', () => {
  const a = makeOpId()
  const b = makeOpId()
  assert.ok(a && b && a !== b)
})

test('OP_TYPES_AUTORISES ne contient QUE les 4 opérations de relevé', () => {
  assert.deepEqual(
    [...OP_TYPES_AUTORISES].sort(),
    ['releve.cote', 'releve.obstacle', 'releve.photo', 'releve.reponse_qr'].sort(),
  )
})

test('enqueue accepte les 4 types de relevé et persiste via le store', async () => {
  const store = memoryStore()
  const fr = new FileReleve({ store, sender: async () => ({ results: [] }) })
  for (const opType of OP_TYPES_AUTORISES) {
    await fr.enqueue(opType, { x: 1 })
  }
  assert.equal(await fr.count(), OP_TYPES_AUTORISES.length)
  // Une nouvelle instance branchée sur le même store retrouve la file persistée.
  const fr2 = new FileReleve({ store, sender: async () => ({ results: [] }) })
  assert.equal(await fr2.count(), OP_TYPES_AUTORISES.length)
})

test('enqueue REFUSE toute opération de calcul ou de génération documentaire', async () => {
  const fr = new FileReleve({ store: memoryStore(), sender: async () => ({ results: [] }) })
  await assert.rejects(
    () => fr.enqueue('calepinage.calculer', { affaire: 1 }),
    /refusé/,
  )
  await assert.rejects(
    () => fr.enqueue('dossier.generer_zip', { affaire: 1 }),
    /refusé/,
  )
  await assert.rejects(
    () => fr.enqueue('pack.generer_piece', {}),
    /refusé/,
  )
  // Aucune de ces tentatives n'a laissé de trace en file (jamais silencieuse).
  assert.equal(await fr.count(), 0)
})

test('flush vide la file quand le serveur confirme (applied)', async () => {
  const { sender } = fakeServer()
  const fr = new FileReleve({ store: memoryStore(), sender })
  await fr.enqueue('releve.cote', { valeur: 3.2 })
  await fr.enqueue('releve.obstacle', { type: 'cheminee' })
  const res = await fr.flush()
  assert.equal(res.flushed, 2)
  assert.equal(res.remaining, 0)
  assert.equal(await fr.count(), 0)
})

test('resynchronisation IDEMPOTENTE : rejouer le même client_op_id après un double envoi n\'est jamais un doublon', async () => {
  const { sender, seen } = fakeServer()
  const store = memoryStore()
  const fr = new FileReleve({ store, sender })
  const id = await fr.enqueue('releve.photo', { fichier: 'a.jpg' })

  // Premier flush : le serveur applique.
  await fr.flush()
  assert.ok(seen.has(id))

  // Simule un rejeu de la MÊME opération (ex. le client n'a jamais vu la
  // réponse et retente au retour réseau) : on la remet en file avec le MÊME
  // client_op_id, jamais un nouvel id généré.
  await fr.enqueue('releve.photo', { fichier: 'a.jpg' }, { clientOpId: id })
  const res = await fr.flush()
  // Le serveur renvoie `replayed` (déjà vu) : l'op est retirée normalement, PAS
  // comptée comme une nouvelle photo.
  assert.equal(res.flushed, 1)
  assert.equal(res.remaining, 0)
})

test('échec réseau du sender : la file reste INTACTE pour réessayer', async () => {
  let calls = 0
  const sender = async () => { calls += 1; throw new Error('network down') }
  const fr = new FileReleve({ store: memoryStore(), sender })
  await fr.enqueue('releve.cote', { valeur: 1 })
  const res = await fr.flush()
  assert.equal(res.flushed, 0)
  assert.equal(await fr.count(), 1)
  assert.equal(calls, 1)
})

test('un CONFLIT serveur est signalé et JAMAIS résolu en silence par le flush', async () => {
  const id0 = makeOpId()
  const { sender } = fakeServer({ conflitPour: new Set([id0]) })
  const fr = new FileReleve({ store: memoryStore(), sender })
  await fr.enqueue('releve.cote', { valeur: 2.5 }, { clientOpId: id0 })

  const res = await fr.flush()
  assert.equal(res.conflicts, 1)
  assert.equal(res.remaining, 1) // toujours en file — pas retiré tout seul

  const conflits = await fr.conflicts()
  assert.equal(conflits.length, 1)
  assert.equal(conflits[0].client_op_id, id0)
  assert.ok(conflits[0].serverConflict)

  // Un second flush ne fait PAS disparaître le conflit tout seul.
  await fr.flush()
  assert.equal((await fr.conflicts()).length, 1)

  // Seule une résolution EXPLICITE le retire.
  await fr.resoudreConflit(id0)
  assert.equal(await fr.count(), 0)
})

test('une op rejetée (erreur serveur, hors conflit) reste en file avec son message, jamais silencieuse', async () => {
  const id0 = makeOpId()
  const { sender } = fakeServer({ erreurPour: new Set([id0]) })
  const fr = new FileReleve({ store: memoryStore(), sender })
  await fr.enqueue('releve.reponse_qr', { reponse: 'x' }, { clientOpId: id0 })

  const res = await fr.flush()
  assert.equal(res.failed, 1)
  const echecs = await fr.failed()
  assert.equal(echecs.length, 1)
  assert.equal(echecs[0].serverError, 'Rejetée.')
  assert.equal(echecs[0].attempts, 1)

  await fr.discard(id0)
  assert.equal(await fr.count(), 0)
})

test('flush concurrent : un second appel pendant le premier est ignoré (skipped), jamais une double soumission', async () => {
  // Le deferred est construit AVANT le premier flush() : `resolveSender` est
  // donc déjà assigné quand on l'appelle plus bas, quel que soit le nombre de
  // microtasks que `flush()` consomme avant d'atteindre `sender(batch)`.
  let resolveSender
  const deferred = new Promise((resolve) => { resolveSender = resolve })
  const sender = () => deferred
  const fr = new FileReleve({ store: memoryStore(), sender })
  await fr.enqueue('releve.cote', { valeur: 1 })

  const p1 = fr.flush()
  const p2 = fr.flush()
  resolveSender({ results: [] })
  const [r1, r2] = await Promise.all([p1, p2])
  const skips = [r1, r2].filter((r) => r.skipped)
  assert.equal(skips.length, 1)
})
