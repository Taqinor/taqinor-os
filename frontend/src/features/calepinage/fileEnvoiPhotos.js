/* ACAL892 — la file d'envoi HORS LIGNE des photos de site du calepinage.
   La file binaire de l'ERP (`createBinaryOutboxStore`, IndexedDB) ne rend qu'un magasin clé/valeur : l'ORDRE, le REJEU
   et le COMPTE sont écrits ici, sur le modèle de `installations/offline/fieldOutbox.js`. `ajouterPhoto` reste l'écrivain.
   Les entrées portent leur propre type (`calepinage.photo`) : le rejeu ne touche que les siennes. Un refus serveur
   (réponse HTTP) retire la photo de la file et nomme le champ fautif ; une coupure réseau la laisse en file. */
import calepinageApi from '../../api/calepinageApi'
import { createBinaryOutboxStore } from '../../lib/offlineStore'
import {
  BINARY_MAX_BYTES, BINARY_MAX_OPS, OutboxQuotaError, espaceDisponible, majAtomique, makeOpId,
} from '../../lib/offlineOutbox'
import { refusServeur } from './commun/refusServeur'

export const OP_PHOTO_CALEPINAGE = 'calepinage.photo'

let magasin = null
const file = () => { magasin ??= createBinaryOutboxStore().store; return magasin }
const miennes = (ops, id) => ops.filter((o) => o.op_type === OP_PHOTO_CALEPINAGE && (id == null || String(o.meta?.calepinageId) === String(id)))

/** Le corps multipart de `ajouterPhoto` (mêmes champs que le dépôt en ligne). */
function corpsPhoto(fichier, { genre, prise_le: priseLe, legende }) {
  const corps = new FormData()
  corps.append('photo', fichier)
  corps.append('genre', genre)
  corps.append('prise_le', priseLe)
  if (legende) corps.append('legende', legende)
  return corps
}

/** Le nombre de photos en attente (celles de ce calepinage si `calepinageId`), lu dans la file : survit au rechargement. */
export async function compterEnAttente(calepinageId) {
  return miennes(await file().load(), calepinageId).length
}

async function mettreEnFile(calepinageId, fichier, champs) {
  const bytes = await fichier.arrayBuffer()
  const dispo = await espaceDisponible(bytes.byteLength)
  const courantes = await file().load()
  if (!dispo || courantes.length >= BINARY_MAX_OPS || courantes.reduce((n, o) => n + (o.size || 0), 0) + bytes.byteLength > BINARY_MAX_BYTES) {
    throw new OutboxQuotaError('File d’envoi pleine : reconnectez-vous au réseau pour la vider avant d’ajouter une photo.')
  }
  const entree = {
    client_op_id: makeOpId(), op_type: OP_PHOTO_CALEPINAGE, meta: { calepinageId, ...champs },
    bytes, name: fichier.name || 'photo.jpg', type: fichier.type || 'image/jpeg', size: bytes.byteLength,
    queuedAt: new Date().toISOString(),
  }
  await majAtomique(file(), (cur) => [...cur, entree])
}

/** Dépose en ligne ; hors ligne (ou coupure : aucune réponse du serveur), range en file. `{ enFile }` ou `{ enFile: false, res }` ; un refus serveur est relancé. */
export async function deposerOuMettreEnFile(calepinageId, fichier, champs) {
  if (typeof navigator !== 'undefined' && navigator.onLine === false) {
    await mettreEnFile(calepinageId, fichier, champs)
    return { enFile: true }
  }
  try {
    return { enFile: false, res: await calepinageApi.calepinages.ajouterPhoto(calepinageId, corpsPhoto(fichier, champs)) }
  } catch (err) {
    if (err?.response) throw err
    await mettreEnFile(calepinageId, fichier, champs)
    return { enFile: true }
  }
}

/** Rejoue DANS L'ORDRE : `{ envoyees, refusees: [{message, champs}], restantes }` ; sans réseau, on s'arrête et la file reste intacte. */
export async function rejouerFile(calepinageId) {
  let envoyees = 0
  const refusees = []
  for (const op of miennes(await file().load(), calepinageId)) {
    try {
      const fichier = new File([op.bytes], op.name, { type: op.type })
      await calepinageApi.calepinages.ajouterPhoto(op.meta.calepinageId, corpsPhoto(fichier, op.meta))
      envoyees += 1
    } catch (err) {
      if (!err?.response) break
      refusees.push(refusServeur(err))
    }
    await majAtomique(file(), (cur) => cur.filter((o) => o.client_op_id !== op.client_op_id))
  }
  return { envoyees, refusees, restantes: await compterEnAttente(calepinageId) }
}
