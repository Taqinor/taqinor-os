// N32 — Helpers purs pour l'archive documentaire (testables sans DOM).
// Les libellés FR des types de document et le tri par date décroissante.

export const TYPE_LABELS = {
  devis: 'Devis',
  facture: 'Facture',
  avoir: 'Avoir',
  bon_commande: 'Bon de commande',
  pv_reception: 'PV de réception',
  bon_livraison: 'Bon de livraison',
  dossier_remise: 'Dossier de remise',
  attestation: 'Attestation',
}

export function typeLabel(doc) {
  return TYPE_LABELS[doc.type] || doc.label || doc.type
}

// Tri du plus récent au plus ancien ; les documents sans date passent en fin.
export function sortDocsDesc(docs) {
  return [...(docs || [])].sort((a, b) => {
    const da = a.date || ''
    const db = b.date || ''
    if (da === db) return 0
    return da < db ? 1 : -1
  })
}
