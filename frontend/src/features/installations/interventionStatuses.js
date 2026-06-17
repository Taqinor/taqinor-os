// F4 — statuts d'intervention (miroir EXACT de installations.Intervention.Statut
// côté backend). Machine à états PROPRE à l'intervention — n'a aucun rapport
// avec le statut du chantier ni le pipeline lead. Pur (testé).

export const INTERVENTION_STATUSES = [
  'a_preparer', 'prete', 'en_route', 'sur_site', 'terminee', 'validee',
]

export const INTERVENTION_STATUS_LABELS = {
  a_preparer: 'À préparer',
  prete: 'Prête',
  en_route: 'En route',
  sur_site: 'Sur site',
  terminee: 'Terminée',
  validee: 'Validée',
}

export const INTERVENTION_STATUS_COLORS = {
  a_preparer: '#64748b',
  prete: '#0d9488',
  en_route: '#2563eb',
  sur_site: '#7c3aed',
  terminee: '#16a34a',
  validee: '#15803d',
}

export const INTERVENTION_TYPE_LABELS = {
  pose: 'Pose',
  raccordement: 'Raccordement',
  mise_en_service: 'Mise en service',
  controle: 'Contrôle',
  depannage: 'Dépannage',
  sav: 'SAV',
  visite: 'Visite',
}

// Statut rabattu sur une colonne valide (toute valeur inconnue → 1re colonne).
export const interventionColumn = (statut) =>
  INTERVENTION_STATUSES.includes(statut) ? statut : INTERVENTION_STATUSES[0]

export const interventionStatusLabel = (statut) =>
  INTERVENTION_STATUS_LABELS[statut] ?? statut ?? '—'

export const interventionTypeLabel = (type) =>
  INTERVENTION_TYPE_LABELS[type] ?? type ?? '—'
