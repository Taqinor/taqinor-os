/* ORDRE FONDATEUR 2026-08-01 — « les leads doivent pouvoir REVENIR EN ARRIÈRE
   d'étape, avec une confirmation avant ».
   ---------------------------------------------------------------------------
   Le recul n'est plus REFUSÉ, il est DEMANDÉ. Ce module tient l'UNIQUE
   formulation de cette question, partagée par les trois surfaces qui peuvent
   faire reculer un lead : le glisser-déposer du board, le sélecteur d'étape
   sous les cartes, et le menu d'étape de la fenêtre lead. Une seule source :
   l'utilisatrice lit exactement la même phrase quel que soit le geste, et une
   retouche de formulation ne peut plus n'en corriger que deux tiers.

   La question NOMME le lead et les DEUX étapes, parce que c'est ce qu'il faut
   pouvoir relire avant de dire oui — « êtes-vous sûr ? » ne se relit pas.
   Elle n'est PAS destructive (`destructive: false`, libellé « Ramener ») :
   rien n'est supprimé, on remonte le pipeline, et un rouge d'alerte
   banaliserait le vrai rouge des suppressions.

   Ce n'est jamais la SEULE garde : sans le marqueur `confirme_recul` dans le
   corps du PATCH, le serveur refuse toujours le recul (garde funnel de
   `LeadSerializer.validate`, apps/crm/serializers.py). La boîte de dialogue
   décide, le serveur vérifie.

   Les clés/libellés d'étape viennent de stages.js UNIQUEMENT (miroir
   STAGES.py, règle #2) — aucun littéral d'étape ici. */
import { useCallback } from 'react'
import { STAGE_LABELS } from './stages'
import { devisAccepteReference, isSortieSigne } from './stages'
import { useConfirmDialog } from '../../ui/confirm'

const libelle = (key) => STAGE_LABELS[key] ?? key

/* Décision fondateur (Reda, 08/10/2026) — QUITTER « Signé » dés-accepte le
   devis côté serveur (retour à « Envoyé », chantier de la signature annulé).
   La question le DIT, en nommant le devis quand la fiche le connaît, et vaut
   aussi pour Froid (qui n'est pas un recul) : les appelants la posent dès
   que `isSortieSigne(lead.stage, cible)`. Si une suite réelle existe
   (facture émise, chantier avancé…), le serveur refuse en 409 et son texte
   est affiché tel quel par l'appelant. */
export const descriptionSortieSigne = (lead) => {
  const ref = devisAccepteReference(lead)
  return `${ref ? `Le devis ${ref}` : 'Le devis accepté'} repassera en `
    + '« Envoyé » et le chantier créé à la signature sera annulé. Continuer ?'
}

/**
 * useConfirmerRecul — hook de confirmation d'un retour en arrière d'étape.
 *
 * @returns {(lead: object, cible: string) => Promise<boolean>} vrai si
 *   l'utilisatrice a confirmé le recul, faux si elle l'a annulé (l'appelant
 *   ne doit alors RIEN faire : pas de PATCH, pas de mise à jour optimiste).
 */
export function useConfirmerRecul() {
  const { confirm } = useConfirmDialog()
  return useCallback(
    (lead, cible) => confirm({
      title: `Ramener « ${lead?.nom || 'ce lead'} » de `
        + `${libelle(lead?.stage)} à ${libelle(cible)} ?`,
      description: isSortieSigne(lead?.stage, cible)
        ? descriptionSortieSigne(lead)
        : "Le lead recule dans l'entonnoir. Le changement est tracé "
          + "dans l'historique du lead.",
      confirmLabel: 'Ramener',
      cancelLabel: 'Annuler',
      destructive: false,
    }),
    [confirm],
  )
}
