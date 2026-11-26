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

// Historique du lead — combien d'entrées le filtre COURANT cache-t-il qui sont plus RÉCENTES que la plus récente des
// entrées visibles ? (aucune visible ⇒ toutes celles que le filtre cache). Les notes épinglées ne servent pas de repère
// (le serveur les sert en tête, quelle que soit leur date). Pur : horodatages comparés en millisecondes.
export function nombreMasquesPlusRecents(entries, filterKey) {
  if (!Array.isArray(entries) || filterKey === 'tous') return 0
  const horo = (a) => Date.parse(a?.created_at) || 0
  let plusRecenteVisible = 0
  for (const a of entries) {
    if (!a?.pinned && matchesTimelineFilter(a.kind, filterKey) && horo(a) > plusRecenteVisible) plusRecenteVisible = horo(a)
  }
  return entries.filter((a) => !matchesTimelineFilter(a.kind, filterKey) && horo(a) > plusRecenteVisible).length
}
