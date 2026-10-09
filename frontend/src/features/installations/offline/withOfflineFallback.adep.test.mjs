// ADEP45 — la clé d'idempotence est générée AVANT l'appel en ligne, transmise à
// l'appel (`client_op_id` du contrat op_terrain_en_ligne.json) et RÉUTILISÉE
// pour l'op filée : après un timeout survenu APRÈS l'effet, le rejeu de la file
// ne crée pas de doublon (le serveur répond `replayed`).
// Le cœur pur est `repliHorsLigne` (outbox.js) — `fieldOutbox.js` en est la
// façade navigateur (axios/IndexedDB, non chargeable sous `node --test`).
// Run with: node --test src/features/installations/offline/
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { FieldOutbox, memoryStore, repliHorsLigne } from './outbox.js'
import { documentContrat } from '../../../test/fixtures/contractSamples.js'

const CONTRAT = documentContrat('installations', 'op_terrain_en_ligne')

// Faux serveur IDEMPOTENT par clé, à la frontière HTTP : même corps que le
// contrat (`client_op_id` + champs), `replayed: true` au second passage.
function serveurIdempotent() {
  const parCle = new Map()
  const effets = []
  return {
    effets,
    post(corps) {
      assert.ok('client_op_id' in CONTRAT.requete, 'le contrat porte client_op_id')
      const cle = corps.client_op_id
      if (cle && parCle.has(cle)) return { ...parCle.get(cle), replayed: true }
      const objet = { id: effets.length + 1, ...corps }
      effets.push(objet)
      if (cle) parCle.set(cle, objet)
      return { ...objet, replayed: false }
    },
  }
}

test('une seule clé : l’appel en ligne et l’op filée la partagent (un seul effet après timeout)', async () => {
  const serveur = serveurIdempotent()
  const outbox = new FieldOutbox({
    store: memoryStore(),
    // Synchro : rejoue chaque op via le MÊME serveur, avec la clé de l'op.
    sender: async (ops) => ({
      results: ops.map((o) => {
        const r = serveur.post({ ...o.payload, client_op_id: o.client_op_id })
        return { client_op_id: o.client_op_id, status: r.replayed ? 'replayed' : 'applied' }
      }),
    }),
  })

  let cleEnLigne = null
  const res = await repliHorsLigne({
    outbox,
    opType: 'intervention.serial',
    payload: { intervention: 41, numero_serie: CONTRAT.requete.numero_serie },
    onlineCall: async (cle) => {
      cleEnLigne = cle
      // L'effet a lieu côté serveur, puis la RÉPONSE expire (pas de `response`).
      serveur.post({ ...CONTRAT.requete, client_op_id: cle })
      throw new Error('timeout of 20000ms exceeded')
    },
  })

  assert.equal(res.queued, true)
  assert.ok(cleEnLigne, 'l’appel en ligne a reçu une clé')
  assert.equal(res.clientOpId, cleEnLigne)
  const [op] = await outbox.pending()
  assert.equal(op.client_op_id, cleEnLigne) // CLAUSE PERSISTANCE : la file porte la clé en ligne

  const bilan = await outbox.flush()
  assert.equal(bilan.flushed, 1)
  assert.equal(serveur.effets.length, 1, 'un seul objet créé après timeout + rejeu')
})

test('succès en ligne : rien en file, clé transmise', async () => {
  const outbox = new FieldOutbox({ store: memoryStore(), sender: async () => ({ results: [] }) })
  let cle = null
  const res = await repliHorsLigne({
    outbox, opType: 'intervention.reserve', payload: {},
    onlineCall: async (c) => { cle = c; return { data: { id: 1 } } },
  })
  assert.equal(res.queued, false)
  assert.ok(cle)
  assert.equal((await outbox.pending()).length, 0)
})

test('erreur applicative (réponse HTTP) : relancée, jamais filée', async () => {
  const outbox = new FieldOutbox({ store: memoryStore(), sender: async () => ({ results: [] }) })
  const erreur = { response: { status: 400, data: { detail: 'non' } } }
  await assert.rejects(
    repliHorsLigne({ outbox, opType: 'x', payload: {}, onlineCall: async () => { throw erreur } }),
    (e) => e === erreur,
  )
  assert.equal((await outbox.pending()).length, 0)
})

test('regénérer la clé dans enqueue doublerait l’effet (garde du test)', async () => {
  const serveur = serveurIdempotent()
  const outbox = new FieldOutbox({
    store: memoryStore(),
    sender: async (ops) => ({
      results: ops.map((o) => {
        const r = serveur.post({ ...o.payload, client_op_id: o.client_op_id })
        return { client_op_id: o.client_op_id, status: r.replayed ? 'replayed' : 'applied' }
      }),
    }),
  })
  // Contre-exemple : clé en ligne ≠ clé filée ⇒ 2 effets (c'est le défaut corrigé).
  serveur.post({ ...CONTRAT.requete, client_op_id: 'cle-en-ligne' })
  await outbox.enqueue('intervention.serial', { ...CONTRAT.requete }, { clientOpId: 'autre-cle' })
  await outbox.flush()
  assert.equal(serveur.effets.length, 2)
})
