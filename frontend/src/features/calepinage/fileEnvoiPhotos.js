/* ACAL892 — la file d'envoi HORS LIGNE des photos de site du calepinage.
   La file binaire de l'ERP (`createBinaryOutboxStore`, IndexedDB) ne rend qu'un magasin clé/valeur : l'ORDRE, le REJEU
   et le COMPTE sont écrits ici, sur le modèle de `installations/offline/fieldOutbox.js`. `ajouterPhoto` reste l'écrivain.
   Les entrées portent leur propre type (`calepinage.photo`) : le rejeu ne touche que les siennes. Un refus serveur
   (réponse HTTP) retire la photo de la file et nomme le champ fautif ; une coupure réseau la laisse en file.
   ACAL1810 — le RELEVÉ de visite tapé hors ligne passe par la MÊME file (type `calepinage.releve`, un seul par calepinage :
   le dernier relevé terminé remplace le précédent) et le même rejeu : aucun second système. */
import calepinageApi from '../../api/calepinageApi'
import { createBinaryOutboxStore } from '../../lib/offlineStore'
import { store } from '../../store'
import {
  BINARY_MAX_BYTES, BINARY_MAX_OPS, OutboxQuotaError, espaceDisponible, majAtomique, makeOpId,
} from '../../lib/offlineOutbox'
import { refusServeur } from './commun/refusServeur'

export const OP_PHOTO_CALEPINAGE = 'calepinage.photo'
export const OP_RELEVE_CALEPINAGE = 'calepinage.releve'

let magasin = null
const file = () => { magasin ??= createBinaryOutboxStore().store; return magasin }
const miennes = (ops, id, type = OP_PHOTO_CALEPINAGE) => ops.filter((o) => o.op_type === type && (id == null || String(o.meta?.calepinageId) === String(id)))

/* ACAL1949 — une entrée gardée (photo ou relevé) appartient à l'utilisateur CONNECTÉ quand il l'a gardée
   (`meta.utilisateurId`) : sur un poste partagé, B ne voit, ne remplace ni ne rejoue jamais ce que A a gardé ; cela
   repart à la reconnexion de A (le relevé avec sa clé `client_op_id`, en `Idempotency-Key`). La déconnexion vide la file
   (`providers/session-bridge.js::emitAuthLogout`). */
const utilisateurCourant = () => { try { return store.getState()?.auth?.user?.id ?? null } catch { return null } }
/** Revue ACAL1949 (point 3) — une entrée gardée SANS utilisateur (avant cette règle, ou sans session connue) est une
    « ancienne » : jamais rejouée seule, jamais jetée en silence ; l'utilisateur connecté la voit et choisit (l'envoyer
    sous son compte, ou la supprimer). */
const estAncienne = (o) => o?.meta?.utilisateurId == null
/** Gardée par l'utilisateur connecté. Session pas encore connue (`null`) : RIEN n'est à lui — rien n'est rejoué,
    retiré ni proposé tant que la session n'est pas là (point 5). */
const duCompte = (o) => {
  const u = utilisateurCourant()
  return u != null && !estAncienne(o) && String(o.meta.utilisateurId) === String(u)
}
/** Revue ACAL1949 (point 4) — les photos de l'utilisateur connecté seulement (même règle que le relevé). */
const photosDuCompte = (ops, id) => miennes(ops, id).filter(duCompte)

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
  return photosDuCompte(await file().load(), calepinageId).length
}

/** T4-X8-003 — les genres des photos en attente (dans l'ordre de la file) : survivent au rechargement, l'écran les montre. */
export async function genresEnAttente(calepinageId) {
  return photosDuCompte(await file().load(), calepinageId).map((o) => o.meta?.genre).filter(Boolean)
}

async function mettreEnFile(calepinageId, fichier, champs) {
  const bytes = await fichier.arrayBuffer()
  const dispo = await espaceDisponible(bytes.byteLength)
  const courantes = await file().load()
  if (!dispo || courantes.length >= BINARY_MAX_OPS || courantes.reduce((n, o) => n + (o.size || 0), 0) + bytes.byteLength > BINARY_MAX_BYTES) {
    throw new OutboxQuotaError('File d’envoi pleine : reconnectez-vous au réseau pour la vider avant d’ajouter une photo.')
  }
  const entree = {
    client_op_id: makeOpId(), op_type: OP_PHOTO_CALEPINAGE,
    meta: { calepinageId, ...champs, utilisateurId: utilisateurCourant() },
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

/** Une réponse qui ne juge pas l'envoi (session expirée, serveur en cours de redémarrage, trop de requêtes) : la garder
    en file et réessayer plus tard. ACAL1949 (revue) — de même le 409 « la MÊME requête est déjà en cours » que
    `core/idempotency.py::IdempotencyEnCours` sert avec `code: 'idempotency_en_cours'` (deux onglets rejouent la même
    clé) : l'autre envoi peut encore échouer, l'entrée reste ; le rejeu suivant reçoit la réponse mémorisée. Tout AUTRE
    409 (même clé, corps différent : `IdempotencyConflict`, sans ce code) reste un vrai refus, dit à l'écran. */
const reponsePassagere = (reponse) => {
  const statut = reponse?.status
  if (statut === 409) return reponse?.data?.code === 'idempotency_en_cours'
  return statut === 401 || statut === 408 || statut === 429 || statut >= 500
}

/** Rejoue DANS L'ORDRE : `{ envoyees, refusees: [{message, champs}], restantes }` ; sans réseau ou sur une réponse
    PASSAGÈRE (ACAL1974 : un 502 pendant un deploy rangeait la photo parmi les « refusées »), on s'arrête et la file
    reste intacte ; seul un vrai refus du serveur retire la photo et la dit. */
export async function rejouerFile(calepinageId) {
  let envoyees = 0
  const refusees = []
  for (const op of photosDuCompte(await file().load(), calepinageId)) {
    try {
      const fichier = new File([op.bytes], op.name, { type: op.type })
      await calepinageApi.calepinages.ajouterPhoto(op.meta.calepinageId, corpsPhoto(fichier, op.meta))
      envoyees += 1
    } catch (err) {
      if (!err?.response || reponsePassagere(err.response)) break
      refusees.push(refusServeur(err))
    }
    await majAtomique(file(), (cur) => cur.filter((o) => o.client_op_id !== op.client_op_id))
  }
  return { envoyees, refusees, restantes: await compterEnAttente(calepinageId) }
}

const releveDuCompte = (o, id) => miennes([o], id, OP_RELEVE_CALEPINAGE).length > 0 && duCompte(o)
const relevesDuCompte = (ops, id) => ops.filter((o) => releveDuCompte(o, id))
const ancienneDe = (o, id) => estAncienne(o)
  && (miennes([o], id, OP_RELEVE_CALEPINAGE).length > 0 || miennes([o], id, OP_PHOTO_CALEPINAGE).length > 0)

/** Les entrées « anciennes » de ce calepinage : `{ releve: bool, photos: n }` (rien sans session connue). */
export async function anciennesEnFile(calepinageId) {
  if (utilisateurCourant() == null) return { releve: false, photos: 0 }
  const anciennes = (await file().load()).filter((o) => ancienneDe(o, calepinageId))
  return {
    releve: anciennes.some((o) => o.op_type === OP_RELEVE_CALEPINAGE),
    photos: anciennes.filter((o) => o.op_type === OP_PHOTO_CALEPINAGE).length,
  }
}

/** « Envoyer sous mon compte » : les anciennes de ce calepinage deviennent celles de l'utilisateur connecté (même clé
    d'idempotence) ; le rejeu ordinaire les envoie ensuite. */
export async function adopterAnciennes(calepinageId) {
  const u = utilisateurCourant()
  if (u == null) return
  await majAtomique(file(), (cur) => cur.map((o) => (ancienneDe(o, calepinageId)
    ? { ...o, meta: { ...o.meta, utilisateurId: u } } : o)))
}

/** « Supprimer » : retire les anciennes de ce calepinage, sur le geste explicite de l'utilisateur connecté. */
export async function supprimerAnciennes(calepinageId) {
  if (utilisateurCourant() == null) return
  await majAtomique(file(), (cur) => cur.filter((o) => !ancienneDe(o, calepinageId)))
}

/** ACAL1810 — garde le relevé terminé (corps de `corpsDuReleve`, id du relevé à corriger ou `null` pour en créer un) :
    le relevé déjà en file de ce calepinage (et de cet utilisateur) est REMPLACÉ, jamais doublé. Pas d'octets : le corps
    tient dans `meta`. */
export async function mettreReleveEnFile(calepinageId, { corps, releveId = null }) {
  const courantes = await file().load()
  const sansLeMien = courantes.filter((o) => !releveDuCompte(o, calepinageId))
  if (sansLeMien.length >= BINARY_MAX_OPS) {
    throw new OutboxQuotaError('File d’envoi pleine : reconnectez-vous au réseau pour la vider avant de terminer le relevé.')
  }
  const entree = {
    client_op_id: makeOpId(), op_type: OP_RELEVE_CALEPINAGE,
    meta: { calepinageId, releveId, corps, utilisateurId: utilisateurCourant() },
    bytes: new ArrayBuffer(0), name: 'releve.json', type: 'application/json', size: 0, queuedAt: new Date().toISOString(),
  }
  await majAtomique(file(), (cur) => [...cur.filter((o) => !releveDuCompte(o, calepinageId)), entree])
}

/** Un relevé de ce calepinage attend-il le réseau ? (lu dans la file : survit au rechargement). */
export async function releveEnAttente(calepinageId) {
  return relevesDuCompte(await file().load(), calepinageId).length > 0
}

/** Retire le relevé en file : l'envoi en ligne vient de réussir, le garder le renverrait une seconde fois. */
export async function oublierReleveEnFile(calepinageId) {
  await majAtomique(file(), (cur) => cur.filter((o) => !releveDuCompte(o, calepinageId)))
}

/** ACAL1949 — vide TOUS les relevés gardés ; les photos ne sont pas touchées. La purge de la DÉCONNEXION ne passe pas
    par ici : `providers/session-bridge.js::emitAuthLogout` vide la file par type, même si ce module n'a jamais été
    chargé dans la page. */
export async function viderRelevesEnFile() {
  await majAtomique(file(), (cur) => cur.filter((o) => o.op_type !== OP_RELEVE_CALEPINAGE))
}

const rejeuxReleve = new Map()

/** Rejoue le relevé en file : `{ envoye, releve, refus: {message, champs} | null, restantes }`. Sans réseau on s'arrête et
    la file reste intacte ; un refus du serveur (réponse HTTP) retire l'entrée et la dit ; deux rejeux simultanés (retour du
    réseau + ouverture de l'écran) n'en font qu'UN : le relevé part une seule fois. */
export function rejouerReleve(calepinageId) {
  const cle = `${utilisateurCourant() ?? ''}:${calepinageId}`
  if (rejeuxReleve.has(cle)) return rejeuxReleve.get(cle)
  const rejeu = (async () => {
    let envoye = false
    let releve = null
    let refus = null
    for (const op of relevesDuCompte(await file().load(), calepinageId)) {
      try {
        const { calepinageId: id, releveId, corps } = op.meta
        const res = await (releveId
          ? calepinageApi.calepinages.corrigerReleve(id, releveId, corps)
          : calepinageApi.calepinages.enregistrerReleve(id, corps, { idempotencyKey: op.client_op_id }))
        envoye = true
        releve = res?.data?.releve ?? null
      } catch (err) {
        // Sans réponse (réseau coupé) ou sur une réponse PASSAGÈRE (session expirée, serveur en cours de
        // redémarrage, trop de requêtes) : le relevé RESTE en file et repartira ; seul un vrai refus du serveur
        // le retire et le dit (critique de la vague B : un 502 pendant un deploy effaçait le relevé).
        if (!err?.response || reponsePassagere(err.response)) break
        refus = refusServeur(err)
      }
      await majAtomique(file(), (cur) => cur.filter((o) => o.client_op_id !== op.client_op_id))
    }
    return { envoye, releve, refus, restantes: relevesDuCompte(await file().load(), calepinageId).length }
  })().finally(() => { rejeuxReleve.delete(cle) })
  rejeuxReleve.set(cle, rejeu)
  return rejeu
}
