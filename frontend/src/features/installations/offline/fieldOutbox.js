// N91/F21 — instance partagée de l'outbox de capture terrain + types d'op.
//
// Un SEUL outbox pour toute l'app (la file est globale au terminal). Les
// panneaux de capture l'importent et y filent leurs actions ; le hook
// `useFieldOutbox` câble le flush automatique au retour du réseau.

import installationsApi from '../../../api/installationsApi'
import { Outbox } from './outbox'
import { createFieldOutboxStore } from './idbStore'

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
