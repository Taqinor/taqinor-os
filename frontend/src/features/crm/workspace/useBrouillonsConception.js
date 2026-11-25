// AGEN12 (constat T4-X4-008) — un brouillon RETOUCHÉ gardé après un changement
// de la fiche (facture d'hiver…) imprime encore l'ancienne valeur : la carte du
// devis dans l'onglet Devis du lead le DIT. Lecture seule de la conception
// servie (`GET conception/<lead>/`, clé `brouillons_a_mettre_a_jour`, contrat
// `apps/ventes/contract_samples/conception_lead.json`) : l'ensemble des ids de
// devis à mettre à jour. Aucune route nouvelle, aucun calcul.
import { useEffect, useState } from 'react'
import ventesApi from '../../../api/ventesApi'

//: La phrase affichée sur la carte d'un brouillon listé.
export const AVIS_BROUILLON_AVANT_CALCUL =
  'Ce brouillon date d’avant le dernier calcul de la fiche : ouvrez-le pour le mettre à jour.'

export function useBrouillonsConception(leadId, cle = '') {
  const [ids, setIds] = useState(() => new Set())
  useEffect(() => {
    let vivant = true
    const lire = async () => {
      if (!leadId) { setIds(new Set()); return }
      try {
        const { data } = await ventesApi.getConceptionLead(leadId)
        if (vivant) setIds(new Set((data?.brouillons_a_mettre_a_jour || []).map((b) => b.devis)))
      } catch {
        if (vivant) setIds(new Set())  // aucune conception rangée : rien à dire
      }
    }
    lire()
    return () => { vivant = false }
  }, [leadId, cle])
  return ids
}
