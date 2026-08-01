// EZ14 — UNDO UNIVERSEL : « appliquer TOUT DE SUITE + inverse à l'annulation ».
// ----------------------------------------------------------------------------
// Carte de couverture : seuls des câblages PONCTUELS existaient (VX95 sur
// l'archivage, NTUX6) — aucun mécanisme générique, dans aucun plan.
//
// LE DANGER QU'ON REFUSE (critique vérifiée) : `toastWithUndo` (lib/toast.js)
// accepte un `onCommit` qui est un COMMIT DIFFÉRÉ (`setTimeout` de 6 s). Sur un
// BOARD, l'utilisateur navigue, filtre, change de vue — le composant se démonte
// et le timer part avec la page : l'écriture est PERDUE, silencieusement, alors
// que l'écran a dit « c'est fait ». `resilientMutation` ne sauve pas non plus :
// c'est une file de reprise réseau, pas un rollback.
//
// LA DOCTRINE (publiée dans /ui, UIShowcase) :
//   • ON APPLIQUE TOUT DE SUITE. L'écran ne ment jamais : ce qui est affiché
//     est ce qui est enregistré. Rien n'attend la fin d'un toast.
//   • « Annuler » exécute l'APPEL INVERSE — une seconde écriture, explicite,
//     que le serveur revalide comme n'importe quelle autre.
//   • Donc naviguer, fermer l'onglet ou perdre le réseau pendant le toast ne
//     peut RIEN perdre : il n'y a rien en attente.
//
// QUAND UNDO, QUAND CONFIRMER :
//   • UNDO — l'action est réversible par une écriture inverse propre, et la
//     refaire à l'envers ne coûte rien à personne (étape hors funnel d'argent,
//     assignation, tags, priorité, canal, archivage, statut d'intervention).
//   • CONFIRMER — l'argent (devis/facture/paiement/remise), une suppression
//     dure, un ENVOI (e-mail, WhatsApp, PDF au client). Un e-mail parti ne se
//     dé-envoie pas : proposer « Annuler » y serait un mensonge.
//
// EFFET SUR LE CHATTER, assumé et documenté : l'annulation crée une SECONDE
// ligne d'historique (« annulé »), elle n'efface pas la première. L'historique
// raconte ce qui s'est passé, pas ce qu'on aurait voulu.
//
// @coord NTUX27 — `duration` est un paramètre : quand le réglage tenant
// `duree_undo_toast` existera, il alimentera cet argument, sans toucher aucun
// site d'appel.
import { toastWithUndo, toastError } from './toast'

/** Durée par défaut de la fenêtre « Annuler » (ms). */
export const UNDO_DURATION_MS = 6000

/* ── LE REGISTRE FERMÉ ───────────────────────────────────────────────────────
   Une mutation ne peut passer par l'undo QUE si son genre est déclaré ici.
   C'est une liste blanche : ajouter un genre est un geste délibéré, revu, et
   la garde ci-dessous refuse tout ce qui touche à l'argent, aux suppressions
   dures ou aux envois — même si quelqu'un l'ajoutait par distraction. */
export const UNDO_REGISTRY = {
  // Étape du lead HORS funnel d'argent. `SIGNED` en est exclu par construction :
  // y entrer exige le dialogue d'acceptation (devis + option), jamais un PATCH.
  lead_stage: "Étape du lead (hors passage en « Signé »)",
  lead_owner: 'Responsable du lead',
  lead_tags: 'Étiquettes du lead',
  lead_priorite: 'Priorité du lead',
  lead_canal: 'Canal du lead',
  lead_relance: 'Date de relance du lead',
  lead_archive: 'Archivage / restauration du lead',
  intervention_statut: "Statut d'intervention (recul autorisé côté serveur)",
}

/* Mots qui trahissent une mutation d'ARGENT, une suppression DURE ou un ENVOI.
   La garde est volontairement large : un faux positif se corrige en nommant
   mieux le genre ; un faux négatif, lui, offre « Annuler » sur un e-mail déjà
   parti. */
const INTERDIT = /devis|facture|montant|prix|paiement|total|remise|tva|encaiss|avoir|delete|suppression|supprim|envoi|envoy|email|mail|whatsapp|sms|pdf/i

/** Genres autorisés, dans l'ordre du registre (utile aux tests et à la doc). */
export const UNDO_KINDS = Object.keys(UNDO_REGISTRY)

/**
 * assertUndoable — refuse un genre absent du registre, ou dont le nom trahit
 * une mutation d'argent / de suppression dure / d'envoi. Lève : on préfère un
 * échec bruyant en développement à un « Annuler » trompeur en production.
 */
export function assertUndoable(kind) {
  if (!Object.prototype.hasOwnProperty.call(UNDO_REGISTRY, kind)) {
    throw new Error(`mutateWithUndo : genre « ${kind} » hors du registre fermé (lib/mutateWithUndo.js).`)
  }
  if (INTERDIT.test(kind)) {
    throw new Error(`mutateWithUndo : « ${kind} » touche à l'argent, à une suppression dure ou à un envoi — pas d'undo, une confirmation.`)
  }
  return true
}

/**
 * mutateWithUndo — applique une mutation IMMÉDIATEMENT et offre l'inverse.
 *
 * @param {object}   o
 * @param {string}   o.kind        genre du registre fermé (obligatoire).
 * @param {string}   o.message     texte du toast (« Étape modifiée. »).
 * @param {string}  [o.description]
 * @param {Function} o.apply       l'écriture RÉELLE. Attendue (await) — jamais différée.
 * @param {Function} o.revert      l'écriture INVERSE, exécutée au clic « Annuler ».
 * @param {Function} [o.optimistic]        MAJ d'écran avant l'aller-retour serveur.
 * @param {Function} [o.rollbackOptimistic] remet l'écran d'aplomb si `apply` échoue.
 * @param {string}  [o.errorMessage]
 * @param {number}  [o.duration]   fenêtre « Annuler » (ms) — @coord NTUX27.
 * @returns {Promise<boolean>} true si la mutation a été appliquée.
 */
export async function mutateWithUndo({
  kind,
  message,
  description,
  apply,
  revert,
  optimistic,
  rollbackOptimistic,
  errorMessage = "L'enregistrement a échoué — réessayez.",
  duration = UNDO_DURATION_MS,
}) {
  assertUndoable(kind)
  if (typeof apply !== 'function' || typeof revert !== 'function') {
    throw new Error('mutateWithUndo : `apply` et `revert` sont obligatoires.')
  }

  try { optimistic?.() } catch { /* une MAJ d'écran ne doit jamais casser l'écriture */ }

  try {
    // APPLIQUÉ TOUT DE SUITE. Pas de setTimeout, pas de commit différé : quand
    // cette ligne est franchie, le serveur a répondu.
    await apply()
  } catch (err) {
    try { rollbackOptimistic?.() } catch { /* idem */ }
    toastError(errorMessage)
    return false
  }

  // `onCommit` n'est JAMAIS fourni : c'est lui, et lui seul, qui rendait
  // `toastWithUndo` capable de perdre une écriture au démontage.
  toastWithUndo({
    message,
    description,
    duration,
    onUndo: async () => {
      try {
        await revert()
      } catch {
        toastError("Annulation impossible — vérifiez votre connexion.")
      }
    },
  })
  return true
}

export default mutateWithUndo
