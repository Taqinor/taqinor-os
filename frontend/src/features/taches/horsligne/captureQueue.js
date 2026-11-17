import { useSyncExternalStore } from 'react'
import { Outbox } from '../../../lib/offlineOutbox'
import { createModuleOutboxStore } from '../../../lib/offlineStore'
import {
  classerErreur, planifierTache, saisieRapide, terminerTache,
} from '../../../api/tachesApi'
import { frenchError } from '../../../lib/frenchError'
import { EVENEMENT_DECONNEXION, viderCache } from './cacheJournee'

/* ============================================================================
   TCH100 — La file d'envoi hors ligne du module Tâches : UN `Outbox` (lib/offlineOutbox.js — le moteur unique de
   l'application, jamais un second) sur `createModuleOutboxStore('taches')`. Trois gestes se mettent en file quand
   le réseau manque : AJOUTER (`saisie-rapide/`, `client_id`), COCHER (`terminer/`), REPORTER (`planifier/`,
   `lock_version` du cache). Le reste de l'app est grisé hors ligne (coquille, `useEnLigne`).
   Sources : reference/api.md §5, reference/regles.md « Hors ligne et conflit entre appareils » ; textes.md §2.1.
   RÈGLES (donnees.md inv. 31) :
     · chaque op porte le compte qui l'a faite (`user_id`, `company_id`) et envoie `proprietaire_attendu` ;
     · une op d'un AUTRE compte n'est jamais envoyée : jetée (jamais écrite chez le mauvais propriétaire) —
       qu'on le sache ici (compte courant ≠ compte de l'op) ou par le 409 `autre_compte` du serveur ;
     · un 409 `conflit_version` n'écrase rien : l'op reste en file, le conflit est rendu à la coquille (bandeau
       « Garder la mienne · Prendre l'autre ») ;
     · rejeu SÛR : l'`Idempotency-Key` est le `client_op_id` ; une coupure en plein rejeu laisse la file intacte ;
     · tout (file, cache) est vidé à `taqinor:auth-logout` (poste partagé).
   ========================================================================== */

export const TYPES = { AJOUTER: 'ajouter', COCHER: 'cocher', REPORTER: 'reporter' }
export const MESSAGE_AUTRE_COMPTE = "Une action d'un autre compte a été retirée de la file."
/** Toast d'un geste mis en file (textes.md §2.15 « Hors ligne »). */
export const MESSAGE_EN_FILE = 'Partira dès le retour du réseau'

let compte = null
const ecouteurs = new Set()
const conflits = new Map() // client_op_id → { lockVersion, actuel }
const jetees = []

/** Pose le compte qui écrit (la coquille l'appelle avec l'utilisateur connecté). `null` : plus personne. */
export function definirCompteFile(userId, companyId = null) {
  compte = Number.isInteger(userId) ? { userId, companyId } : null
}

export const compteFile = () => compte

let version = 0
function notifier() {
  version += 1
  for (const cb of [...ecouteurs]) cb()
}

/** S'abonne aux changements de la file (mise en file, rejeu, conflit, abandon). */
export function observerFile(cb) {
  ecouteurs.add(cb)
  return () => ecouteurs.delete(cb)
}

// ── Rejeu ────────────────────────────────────────────────────────────────────

/** Une op transitoire (coupure, 401, 408, 429, 5xx) : on ne tranche pas, la file reste intacte. */
const transitoire = (err) => {
  const statut = err?.response?.status
  return !statut || statut === 401 || statut === 408 || statut === 429 || statut >= 500
}

function envoyer(op) {
  const { corps, tacheId, userId } = op.payload
  const options = { proprietaire: userId }
  if (op.op_type === TYPES.AJOUTER) {
    return saisieRapide({ ...corps, apercu: false }, { ...options, cle: op.client_op_id })
  }
  if (op.op_type === TYPES.COCHER) return terminerTache(tacheId, {}, options)
  return planifierTache(tacheId, corps, options)
}

/** Rejoue UNE op ; rend le résultat attendu par `Outbox.flush` ({ client_op_id, status, error? }). */
async function rejouerUne(op) {
  const id = op.client_op_id
  if (!compte || op.payload.userId !== compte.userId) {
    jetees.push(op)
    return { client_op_id: id, status: 'replayed' }
  }
  try {
    await envoyer(op)
    return { client_op_id: id, status: 'applied' }
  } catch (err) {
    if (transitoire(err)) throw err
    const classe = classerErreur(err)
    if (classe.code === 'autre_compte') {
      jetees.push(op)
      return { client_op_id: id, status: 'replayed' }
    }
    if (classe.code === 'conflit_version') {
      conflits.set(id, { lockVersion: classe.lockVersion, actuel: classe.actuel })
      return { client_op_id: id, status: 'error', error: 'conflit_version' }
    }
    return { client_op_id: id, status: 'error', error: frenchError(err, 'Refusée par le serveur.') }
  }
}

async function sender(lot) {
  const results = []
  for (const op of lot) results.push(await rejouerUne(op))
  return { results }
}

// ── La file ──────────────────────────────────────────────────────────────────

/** Fabrique une file (tests : `store` et `sender` injectés). Défaut : le store du module `taches`. */
export function creerFile({ store = createModuleOutboxStore('taches'), envoi = sender } = {}) {
  return new Outbox({ store, sender: envoi })
}

let file = null
/** La file de l'application (créée au premier accès). */
export function fileTaches() {
  if (!file) file = creerFile()
  return file
}

/** Remplace la file (tests) ; sans argument, rétablit celle de l'application. */
export function remplacerFile(autre = null) {
  file = autre
  conflits.clear()
  jetees.length = 0
}

async function enfiler(type, donnees, cible, f = fileTaches()) {
  if (!compte) throw new Error('Aucun compte connecté : l\'action ne peut pas être mise en file.')
  const payload = { type, ...donnees, userId: compte.userId, companyId: compte.companyId }
  const id = await f.enqueue(type, payload, { target: cible, queuedAt: new Date().toISOString() })
  notifier()
  return id
}

/** Ajouter : `lignes` = les lignes de `saisie-rapide/` (chacune porte son `client_id`). */
export const enfilerAjout = (lignes, f) => enfiler(TYPES.AJOUTER, { corps: { lignes } }, undefined, f)
/** Cocher une tâche (`terminer/`). */
export const enfilerCoche = (tacheId, f) => enfiler(TYPES.COCHER, { tacheId }, tacheId, f)
/** Reporter : `corps` = `{ jour_prevu, moment, heure_debut, quelque_jour, lock_version }` (version du cache). */
export const enfilerReport = (tacheId, corps, f) => enfiler(TYPES.REPORTER, { tacheId, corps }, tacheId, f)

/**
 * Rejoue la file. Rend `{ flushed, failed, remaining, jetees }`. Hors ligne ou sans compte : ne fait rien.
 * `jetees` = les ops retirées parce qu'elles venaient d'un autre compte.
 */
export async function rejouerFile(f = fileTaches()) {
  if (!compte || (typeof navigator !== 'undefined' && navigator.onLine === false)) return null
  const resultat = await f.flush().catch(() => null)
  const retirees = jetees.splice(0)
  notifier()
  return resultat ? { ...resultat, jetees: retirees } : null
}

/** Abandon explicite d'une op refusée ou en conflit. */
export async function abandonner(clientOpId, f = fileTaches()) {
  await f.discard(clientOpId)
  conflits.delete(clientOpId)
  notifier()
}

/** « Garder la mienne » : la même action repart avec le `lock_version` de l'autre appareil. */
export async function garderLaMienne(clientOpId, f = fileTaches()) {
  const op = (await f.pending()).find((x) => x.client_op_id === clientOpId)
  const conflit = conflits.get(clientOpId)
  if (!op || !conflit) return null
  const corps = { ...(op.payload.corps ?? {}), lock_version: conflit.lockVersion }
  await abandonner(clientOpId, f)
  const id = await f.enqueue(op.op_type, { ...op.payload, corps }, { target: op.target, queuedAt: new Date().toISOString() })
  notifier()
  return id
}

/** « Prendre l'autre » : l'op est abandonnée, l'état de l'autre appareil (`actuel`) fait foi. */
export async function prendreLAutre(clientOpId, f = fileTaches()) {
  const conflit = conflits.get(clientOpId)
  await abandonner(clientOpId, f)
  return conflit?.actuel ?? null
}

/** État lu par l'écran : { enAttente, refusees, conflits: [{ opId, lockVersion, actuel }] }. */
export async function etatFile(f = fileTaches()) {
  const ops = await f.pending()
  return {
    enAttente: ops.filter((op) => !op.serverError).length,
    refusees: ops.filter((op) => op.serverError && !conflits.has(op.client_op_id)),
    conflits: ops.filter((op) => conflits.has(op.client_op_id)).map((op) => ({ opId: op.client_op_id, ...conflits.get(op.client_op_id) })),
  }
}

// ── Branchements ─────────────────────────────────────────────────────────────

/**
 * Au retour du réseau (`online`) la file se rejoue ; à la déconnexion (`taqinor:auth-logout`) file ET cache sont
 * vidés. `surJetees(n)` est appelé quand des ops d'un autre compte ont été retirées. Rend le débranchement.
 */
export function brancherRejeu({ surJetees, f = fileTaches() } = {}) {
  if (typeof window === 'undefined') return () => {}
  const surEnLigne = async () => {
    const res = await rejouerFile(f)
    if (res?.jetees.length) surJetees?.(res.jetees.length)
  }
  const surDeconnexion = async () => {
    await f.clear()
    conflits.clear()
    viderCache()
    notifier()
  }
  window.addEventListener('online', surEnLigne)
  window.addEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
  return () => {
    window.removeEventListener('online', surEnLigne)
    window.removeEventListener(EVENEMENT_DECONNEXION, surDeconnexion)
  }
}

const lireVersion = () => version
/** Le nombre de changements vus de la file : l'écran se relit quand il bouge (`useSyncExternalStore`). */
export function useVersionFile() {
  return useSyncExternalStore(observerFile, lireVersion, lireVersion)
}
