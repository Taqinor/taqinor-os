/** « Nom Prénom » d'un lead pour les messages des modales (repli « ce lead »). */
export const nomLeadModale = (lead) =>
  `${lead.nom ?? ''} ${lead.prenom ?? ''}`.trim() || 'ce lead'
