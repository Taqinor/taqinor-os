// NTMOB1 — tests de la file hors-ligne GÉNÉRALISÉE (multi-module).
// Run: node --test src/lib/offlineOutbox.test.mjs
//
// Le scénario du plan : une action CRM posée hors-ligne (noter un lead) est
// mise en file, puis appliquée UNE SEULE FOIS à la reconnexion — même si le
// flush est rejoué deux fois (réponse serveur perdue, onglet rechargé…).
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  OFFLINE_MODULES, Outbox, countByPayloadKey, discardModuleOp,
  flushModuleOutboxes, getModuleOutbox, notifyOfflineOutboxChange,
  onOfflineOutboxChange, pendingCountByTarget, pendingModuleOps,
  purgeModuleOutboxes, queueIfOffline, queueOperation, setModuleSender,
} from './offlineOutbox.js'
// L'ancien chemin terrain doit rester utilisable — il RÉEXPORTE ce moteur.
import { Outbox as OutboxTerrain } from '../features/installations/offline/outbox.js'

// Serveur factice : dédoublonne par client_op_id (contrat d'idempotence du
// point de synchro `POST /offlinesync/operations/batch/`).
function fakeServer({ refuse = () => null, perdreLaReponse = false } = {}) {
  const applied = []      // ops réellement APPLIQUÉES (l'effet métier)
  const vues = new Set()
  let perdre = perdreLaReponse
  const sender = async (ops) => {
    const results = ops.map((op) => {
      const motif = refuse(op)
      if (motif) return { client_op_id: op.client_op_id, status: 'error', error: motif }
      if (vues.has(op.client_op_id)) {
        return { client_op_id: op.client_op_id, status: 'replayed', result: {} }
      }
      vues.add(op.client_op_id)
      applied.push(op)
      return { client_op_id: op.client_op_id, status: 'applied', result: {} }
    })
    if (perdre) {
      // L'effet a eu lieu côté serveur mais la réponse n'arrive jamais : le
      // terminal garde l'op en file et la rejouera.
      perdre = false
      throw Object.assign(new Error('réseau coupé'), { response: undefined })
    }
    return { results }
  }
  return { sender, applied, vues }
}

async function reset() {
  await purgeModuleOutboxes()
  setModuleSender()
}

test('les modules déclarés sont ceux du backend (OfflineOperation.Module)', () => {
  assert.deepEqual(OFFLINE_MODULES,
    ['crm', 'ventes', 'stock', 'installations', 'sav'])
  assert.throws(() => getModuleOutbox('marketing'), /Module hors-ligne inconnu/)
})

test('UN SEUL moteur : le chemin terrain réexporte la même classe', () => {
  assert.equal(OutboxTerrain, Outbox)
})

test('une op filée porte sa clé, son module, sa cible et son horodatage', async () => {
  await reset()
  const id = await queueOperation('crm', 'crm.lead.noter',
    { lead: 7, body: 'Client rappelé depuis le toit' }, { target: 7 })
  const ops = await pendingModuleOps()
  assert.equal(ops.length, 1)
  const [op] = ops
  assert.equal(op.client_op_id, id)
  assert.equal(op.module, 'crm')
  assert.equal(op.op_type, 'crm.lead.noter')
  assert.equal(op.target, 7)
  assert.ok(op.queued_at, 'l’horodatage terminal accompagne l’op')
  await reset()
})

test('appliquée UNE SEULE FOIS même si le flush est rejoué deux fois', async () => {
  await reset()
  const serveur = fakeServer()
  setModuleSender(serveur.sender)
  await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'Note' }, { target: 7 })

  const premier = await flushModuleOutboxes()
  assert.equal(premier.flushed, 1)
  assert.equal((await pendingModuleOps()).length, 0)

  // Rejeu complet : plus rien en file, donc AUCUN second effet.
  const second = await flushModuleOutboxes()
  assert.equal(second.flushed, 0)
  assert.equal(serveur.applied.length, 1, 'l’effet métier n’a lieu qu’une fois')
  await reset()
})

test('réponse serveur perdue : l’op reste en file et le rejeu est un no-op', async () => {
  await reset()
  const serveur = fakeServer({ perdreLaReponse: true })
  setModuleSender(serveur.sender)
  await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'Note' }, { target: 7 })

  await flushModuleOutboxes()                       // effet appliqué, réponse perdue
  assert.equal((await pendingModuleOps()).length, 1, 'rien n’est perdu')

  const rejeu = await flushModuleOutboxes()          // le serveur répond « replayed »
  assert.equal(rejeu.flushed, 1)
  assert.equal((await pendingModuleOps()).length, 0)
  assert.equal(serveur.applied.length, 1, 'toujours UN SEUL effet métier')
  await reset()
})

test('op refusée : elle ne disparaît jamais en silence (VX119)', async () => {
  await reset()
  const serveur = fakeServer({ refuse: () => 'Lead inconnu.' })
  setModuleSender(serveur.sender)
  const id = await queueOperation('crm', 'crm.lead.noter', { lead: 999, body: 'x' },
    { target: 999 })

  const res = await flushModuleOutboxes()
  assert.equal(res.failed, 1)
  const [op] = await pendingModuleOps()
  assert.equal(op.serverError, 'Lead inconnu.')
  assert.equal(op.attempts, 1)

  // Seul un abandon EXPLICITE la retire.
  await discardModuleOp(id)
  assert.equal((await pendingModuleOps()).length, 0)
  await reset()
})

test('compteur par enregistrement pour le badge de liste (NTMOB24)', async () => {
  await reset()
  await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'a' }, { target: 7 })
  await queueOperation('crm', 'crm.lead.tag', { lead: 7, tag: 'chaud' }, { target: 7 })
  await queueOperation('crm', 'crm.lead.noter', { lead: 9, body: 'b' }, { target: 9 })
  await queueOperation('crm', 'crm.lead.noter', { lead: 0, body: 'sans cible' })

  const compte = await pendingCountByTarget('crm')
  assert.equal(compte.get('7'), 2)
  assert.equal(compte.get('9'), 1)
  assert.equal(compte.size, 2, 'une op sans cible n’apparaît sur aucune ligne')
  // Un module jamais utilisé n'ouvre aucune file (donc aucun compteur).
  assert.equal((await pendingCountByTarget('stock')).size, 0)
  await reset()
})

test('queueIfOffline : file sur panne réseau, relance une erreur applicative', async () => {
  await reset()
  const reseauKo = async () => { throw Object.assign(new Error('offline'), { response: undefined }) }
  const refus = async () => { throw Object.assign(new Error('400'), { response: { status: 400 } }) }

  const file = await queueIfOffline('crm', reseauKo, 'crm.lead.noter',
    { lead: 7, body: 'x' }, { target: 7 })
  assert.equal(file.queued, true)
  assert.equal((await pendingModuleOps()).length, 1)

  await assert.rejects(() => queueIfOffline('crm', refus, 'crm.lead.noter',
    { lead: 7, body: 'x' }, { target: 7 }), /400/)
  assert.equal((await pendingModuleOps()).length, 1, 'un refus 4xx n’est jamais filé')

  const ok = await queueIfOffline('crm', async () => 'fait', 'crm.lead.noter', {})
  assert.deepEqual(ok, { queued: false, data: 'fait' })
  await reset()
})

test('les abonnés (badge d’en-tête, badges de liste) sont notifiés', async () => {
  await reset()
  let appels = 0
  const desabonner = onOfflineOutboxChange(() => { appels += 1 })
  await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'x' }, { target: 7 })
  assert.equal(appels, 1)
  // La file TERRAIN (autre module de code) signale son changement par ce même
  // canal : un seul badge, une seule notification.
  notifyOfflineOutboxChange()
  assert.equal(appels, 2)
  desabonner()
  await queueOperation('crm', 'crm.lead.noter', { lead: 7, body: 'y' }, { target: 7 })
  assert.equal(appels, 2, 'le désabonnement coupe bien la notification')
  await reset()
})

test('NTMOB24 — comptage par clé de corps (file terrain : payload.chantier)', () => {
  const compte = countByPayloadKey([
    { payload: { chantier: 9 } },
    { payload: { chantier: 9 } },
    { payload: { chantier: 12 } },
    { payload: { intervention: 3 } },   // autre clé : ignorée
    { payload: {} },
    {},                                  // op sans corps : jamais un plantage
  ], 'chantier')
  assert.equal(compte.get('9'), 2)
  assert.equal(compte.get('12'), 1)
  assert.equal(compte.size, 2)
  assert.equal(countByPayloadKey(undefined, 'chantier').size, 0)
})
