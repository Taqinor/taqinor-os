// AGEN12 (constat T4-X4-008) — un brouillon RETOUCHÉ gardé après un changement
// de la fiche (facture d'hiver…) imprime encore l'ancienne valeur : la carte du
// devis dans l'onglet Devis du lead le DIT. Lecture seule de la conception
// servie (`GET conception/<lead>/`, clé `brouillons_a_mettre_a_jour`, contrat
// `apps/ventes/contract_samples/conception_lead.json`) : l'ensemble des ids de
// devis à mettre à jour. Aucune route nouvelle, aucun calcul.
import { useMemo } from 'react'
import useConceptionLead from './useConceptionLead'

//: La phrase affichée sur la carte d'un brouillon listé.
export const AVIS_BROUILLON_AVANT_CALCUL =
  'Ce brouillon date d’avant le dernier calcul de la fiche : ouvrez-le pour le mettre à jour.'

// R5A-N6 — plus de lecture propre : la conception du lead est lue UNE fois par fiche (useConceptionLead), partagée avec la
// carte « Conception » ; un 404 (aucune conception rangée) = « rien à dire ». Elle est relue par les ACTIONS (fiche
// enregistrée, devis créé ou modifié : `relireConceptionLead`), plus par un changement de la liste des devis.
export function useBrouillonsConception(leadId) {
  const { donnees } = useConceptionLead(leadId)
  return useMemo(
    () => new Set((donnees?.brouillons_a_mettre_a_jour || []).map((b) => b.devis)),
    [donnees],
  )
}
