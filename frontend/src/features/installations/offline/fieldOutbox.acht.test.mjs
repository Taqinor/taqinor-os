// ACHT33 — l'outbox terrain horodate chaque op à la SAISIE (`client_ts`), porte
// `base_updated_at`, et garde EN FILE une op revenue `conflit` (valeur serveur,
// rejouer ou abandonner) au lieu de la marquer appliquée.
// Le test IMPORTE le contrat partagé `field_sync_ops.json` : jamais un mock
// inventé. Run with: node --test src/features/installations/offline/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  FieldOutbox, memoryStore, conflitEnErreur, estConflit, CONFLIT_PREFIX,
} from './outbox.js'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('installations', 'field_sync_ops')
const [OP_CHECKIN, OP_CONSO] = CONTRAT.requete.ops

// Faux serveur = la réponse COMMITTÉE du contrat (check-in appliqué, saisie de
// consommation en `conflit`).
function fileSaisie() {
  const sent = []
  const sender = async (ops) => { sent.push(ops); return conflitEnErreur(CONTRAT.exemple) }
  return { ob: new FieldOutbox({ store: memoryStore(), sender }), sent }
}

test('horodate à la saisie', async () => {
  const { ob, sent } = fileSaisie()
  await ob.enqueue(OP_CHECKIN.op_type, OP_CHECKIN.payload, {
    clientOpId: OP_CHECKIN.client_op_id, clientTs: OP_CHECKIN.client_ts,
  })
  await ob.enqueue(OP_CONSO.op_type, OP_CONSO.payload, {
    clientOpId: OP_CONSO.client_op_id, clientTs: OP_CONSO.client_ts,
    baseUpdatedAt: OP_CONSO.base_updated_at,
  })
  const [checkin, conso] = await ob.pending()
  assert.equal(checkin.client_ts, '2026-10-01T08:00:00Z')
  assert.equal(conso.client_ts, '2026-10-01T09:30:00Z')
  assert.equal(conso.base_updated_at, '2026-09-30T16:00:00Z')
  assert.equal('base_updated_at' in checkin, false)
  // Même forme d'op que celle du contrat partagé.
  assert.deepEqual(checkin, OP_CHECKIN)
  assert.deepEqual(conso, OP_CONSO)
  await ob.flush()
  assert.deepEqual(sent[0].map((o) => o.client_ts), [OP_CHECKIN.client_ts, OP_CONSO.client_ts])
})

test('sans client_ts fourni, l’instant de la mise en file est posé', async () => {
  const { ob } = fileSaisie()
  const avant = Date.now()
  await ob.enqueue('intervention.retour', { intervention: 41 })
  const [op] = await ob.pending()
  assert.ok(Date.parse(op.client_ts) >= avant - 1000)
})

test('conserve l’op en conflit', async () => {
  const { ob } = fileSaisie()
  await ob.enqueue(OP_CHECKIN.op_type, OP_CHECKIN.payload, {
    clientOpId: OP_CHECKIN.client_op_id, clientTs: OP_CHECKIN.client_ts,
  })
  await ob.enqueue(OP_CONSO.op_type, OP_CONSO.payload, {
    clientOpId: OP_CONSO.client_op_id, clientTs: OP_CONSO.client_ts,
    baseUpdatedAt: OP_CONSO.base_updated_at,
  })
  const res = await ob.flush()
  assert.equal(res.flushed, 1) // le check-in seul est appliqué
  assert.equal(res.failed, 1)
  const restantes = await ob.pending()
  assert.equal(restantes.length, 1)
  const [conflit] = restantes
  assert.equal(conflit.client_op_id, OP_CONSO.client_op_id)
  assert.ok(estConflit(conflit))
  assert.ok(conflit.serverError.startsWith(CONFLIT_PREFIX))
  assert.match(conflit.serverError, /corrigee en ligne/)
  assert.match(conflit.serverError, /5\.000/) // valeur serveur visible

  // Rejouer : marque et base_updated_at retirés, l'op repart telle quelle.
  await ob.rejouer(conflit.client_op_id)
  const [rejouee] = await ob.pending()
  assert.equal(rejouee.serverError, undefined)
  assert.equal(rejouee.base_updated_at, undefined)
  assert.equal(rejouee.client_ts, OP_CONSO.client_ts)

  // Abandonner reste possible sur une op en conflit.
  await ob.flush() // re-conflit (faux serveur figé)
  await ob.discard(OP_CONSO.client_op_id)
  assert.equal((await ob.pending()).length, 0)
})

test('une réponse sans conflit est inchangée', () => {
  const r = { results: [{ client_op_id: 'a', status: 'applied' }] }
  assert.deepEqual(conflitEnErreur(r), r)
  assert.equal(conflitEnErreur(undefined), undefined)
})
