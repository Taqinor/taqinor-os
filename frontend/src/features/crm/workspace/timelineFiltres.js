// ENF22 — filtres du fil Historique (constante + logique pure), séparés du composant
// TimelineTab.jsx (règle react-refresh/only-export-components). Déplacement pur.
export const TIMELINE_FILTERS = [
  { key: 'tous', label: 'Tous' },
  { key: 'notes', label: 'Notes' },
  { key: 'appels', label: 'Appels' },
  { key: 'emails', label: 'E-mails' },
  { key: 'devis', label: 'Devis' },
  { key: 'systeme', label: 'Système' },
]

// Logique pure co-localisée (même motif que `ChatterTimeline.parseMarketingTouch`) :
// testable sans DOM, sans réseau.
export function matchesTimelineFilter(kind, filterKey) {
  switch (filterKey) {
    case 'notes': return kind === 'note'
    case 'appels': return kind === 'appel'
    case 'emails': return kind === 'email'
    case 'devis': return typeof kind === 'string' && kind.startsWith('devis_')
    case 'systeme': return kind === 'creation' || kind === 'modification'
    default: return true
  }
}
