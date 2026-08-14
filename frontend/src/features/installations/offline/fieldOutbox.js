// N91/F21 — instance partagée de l'outbox de capture terrain + types d'op.
//
// Un SEUL outbox pour toute l'app (la file est globale au terminal). Les
// panneaux de capture l'importent et y filent leurs actions ; le hook
// `useFieldOutbox` câble le flush automatique au retour du réseau.

import installationsApi from '../../../api/installationsApi'
import { Outbox, BinaryOutbox, OutboxQuotaError } from './outbox'
import { notifyOfflineOutboxChange, purgeModuleOutboxes } from '../../../lib/offlineOutbox'
import { createFieldOutboxStore, createBinaryOutboxStore } from './idbStore'

// Types d'opérations — DOIVENT correspondre aux clés de FIELD_OP_HANDLERS du
// backend (apps/installations/field_sync.py). Centralisés ici pour éviter les
// chaînes magiques disséminées dans les panneaux.
export const FIELD_OPS = {
  DEPART_DEPOT: 'intervention.depart_depot',
  CHECKIN: 'intervention.checkin',
  RETOUR: 'intervention.retour',
  COCHER_MATERIEL: 'intervention.cocher_materiel',
  COCHER_OUTIL: 'intervention.cocher_outil',
  SERIAL: 'intervention.serial',
  CONSOMMATION_LIGNE: 'intervention.consommation_ligne',
  RESERVE: 'intervention.reserve',
  COCHER_SAFETY: 'intervention.cocher_safety',
  SIGNER_CLIENT: 'intervention.signer_client',
  COCHER_CHECKLIST: 'chantier.cocher_checklist',
}

// `sender` : envoie un paquet au point de synchro et renvoie {results}.
async function sender(ops) {
  const r = await installationsApi.syncField(ops)
  return r.data
}

export const fieldOutbox = new Outbox({
  store: createFieldOutboxStore(),
  sender,
})

// Ops actuellement en erreur serveur (message + compteur de tentatives) —
// jamais retirées silencieusement, voir `Outbox.flush()` (VX119).
export async function failed() {
  return fieldOutbox.failed()
}

// ── EZ8 — file BINAIRE (photos) : MÊME outbox, MÊME badge ───────────────────
// Types d'op binaires (une seule aujourd'hui : la photo d'intervention). Le
// rejeu repasse par l'endpoint multipart EXISTANT `ajouterPhoto` — la file JSON
// `/installations/sync/` ne transporte pas de binaire, et EZ8 n'ajoute AUCUN
// endpoint.
export const BINARY_OPS = {
  PHOTO_INTERVENTION: 'intervention.photo',
}

const _binaryStore = createBinaryOutboxStore()

async function binaryUploader(entry) {
  if (entry.op_type !== BINARY_OPS.PHOTO_INTERVENTION) {
    const err = new Error('Type de charge binaire inconnu.')
    err.response = { data: { detail: 'Type de charge binaire inconnu.' } }
    throw err
  }
  const file = new File([entry.bytes], entry.name || 'photo.jpg',
    { type: entry.type || 'image/jpeg' })
  return installationsApi.ajouterPhoto(
    entry.meta.intervention, file, entry.meta.slot)
}

export const binaryOutbox = new BinaryOutbox({
  store: _binaryStore.store,
  persistent: _binaryStore.persistent,
  uploader: binaryUploader,
})

/**
 * EZ8 — met une photo COMPRESSÉE en file (ArrayBuffer). À n'appeler que sur un
 * échec RÉSEAU : une erreur applicative doit rester visible, pas être filée.
 * Relaie `OutboxQuotaError` (message français prêt à afficher).
 */
export async function queuePhoto(blob, { intervention, slot }) {
  const bytes = await blob.arrayBuffer()
  const id = await binaryOutbox.enqueue(
    BINARY_OPS.PHOTO_INTERVENTION,
    { intervention, slot },
    { bytes, name: blob.name || 'photo.jpg', type: blob.type || 'image/jpeg' },
  )
  notifyOfflineOutboxChange()
  requestBackgroundSync()
  return id
}

export { OutboxQuotaError }

// LW45 — purge à la DÉCONNEXION : sur un terminal PARTAGÉ (atelier, camionnette),
// les photos filées par le technicien A ne doivent pas partir sous le compte de
// B. Même événement window générique que le cache de pré-chargement (le module
// reste pur : aucun import Redux/React).
export const LOGOUT_EVENT = 'taqinor:auth-logout'
export function purgeOutboxes() {
  fieldOutbox.clear().catch(() => undefined)
  binaryOutbox.clear().catch(() => undefined)
  // NTMOB1 — les files des autres modules partent avec (même terminal partagé).
  purgeModuleOutboxes().catch(() => undefined)
}
if (typeof window !== 'undefined') {
  window.addEventListener(LOGOUT_EVENT, purgeOutboxes)
}

// Helper : tente l'appel ONLINE d'abord ; si le réseau échoue (pas de réponse
// serveur), met l'op en file pour synchro ultérieure et renvoie
// { queued: true }. Une vraie erreur applicative (réponse 4xx du serveur) est
// relancée — ce n'est pas un problème réseau, l'utilisateur doit la voir.
export async function withOfflineFallback(onlineCall, opType, payload) {
  try {
    const data = await onlineCall()
    return { queued: false, data }
  } catch (err) {
    const isNetwork = !err?.response // axios : pas de réponse = réseau/timeout
    if (!isNetwork) throw err
    const clientOpId = await fieldOutbox.enqueue(opType, payload)
    // NTMOB24 — le badge d'en-tête ET les badges de liste se rafraîchissent
    // aussitôt (l'utilisateur voit sa modification « en attente » sur la ligne).
    notifyOfflineOutboxChange()
    requestBackgroundSync()
    return { queued: true, clientOpId }
  }
}

// Demande au navigateur une Background Sync : il rejouera l'outbox au retour du
// réseau même si l'onglet est en arrière-plan. Best-effort — non supporté
// partout (le flush au focus / événement « online » reste le filet de sécurité).
export function requestBackgroundSync() {
  try {
    if (typeof navigator !== 'undefined' && 'serviceWorker' in navigator) {
      navigator.serviceWorker.ready
        .then((reg) => reg.sync && reg.sync.register('field-outbox-sync'))
        .catch(() => undefined)
    }
  } catch { /* best-effort */ }
}
