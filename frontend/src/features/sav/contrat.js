// Helpers purs (sans dépendances) pour les contrats de maintenance.
// L'autorité sur « due / à venir » reste le serveur (calcul à la lecture) ;
// ces helpers ne servent qu'à l'affichage et au filtrage côté écran.

export const EMPTY_CONTRAT_FILTERS = { q: '', actif: '' }

// Libellé d'échéance lisible à partir des champs renvoyés par l'API.
export function echeanceLabel(contrat) {
  const n = contrat?.jours_avant_visite
  if (contrat?.est_due) {
    return n != null && n < 0 ? `Visite due (en retard de ${-n} j)` : 'Visite due'
  }
  if (contrat?.est_a_venir) {
    return `À venir dans ${n} j`
  }
  return 'Planifiée'
}

// Couleur d'échéance : due (rouge), bientôt (orange), sinon (vert).
export function echeanceColor(contrat) {
  if (contrat?.est_due) return '#dc2626'
  if (contrat?.est_a_venir) return '#d97706'
  return '#16a34a'
}

// Filtrage local : recherche texte + statut actif/inactif.
export function filterContrats(rows, filters = EMPTY_CONTRAT_FILTERS) {
  const needle = (filters.q || '').trim().toLowerCase()
  return rows.filter((c) => {
    if (filters.actif === 'true' && !c.actif) return false
    if (filters.actif === 'false' && c.actif) return false
    if (!needle) return true
    return [c.libelle, c.client_nom, c.installation_reference]
      .filter(Boolean)
      .some((s) => String(s).toLowerCase().includes(needle))
  })
}
