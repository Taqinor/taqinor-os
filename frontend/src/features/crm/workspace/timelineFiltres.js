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

// Ce que le CLIENT fait sur la page publique de son devis est écrit au chatter du lead en note SYSTÈME (kind « note »,
// aucun `field`) : seul le début du corps le distingue (apps/crm : devis_chatter.noter_devis_ouvert / noter_devis_reouvert,
// cadence_signaux.noter_version_remplacee_ouverte / notifier_signal_lecture / notify_client_contact_request,
// ventes.domain.declin_client.note_declin). Le filtre « Devis » les laisse passer — les entrées DÉJÀ stockées en
// production portent ces mêmes débuts, donc aucune réparation de données.
const DEBUTS_ACTIONS_CLIENT_DEVIS = [
  'Le client a ouvert le devis',
  'Le client a rouvert le devis',
  'Le client a commencé à lire la proposition',
  'Le client relit la section',
  'Le client demande à être contacté',
  'Le client décline la proposition',
  'Ancienne version ',
  'Rappel demandé — opposition',
]

function estActionClientSurDevis(kind, body) {
  return kind === 'note' && typeof body === 'string'
    && DEBUTS_ACTIONS_CLIENT_DEVIS.some((debut) => body.startsWith(debut))
}

// Logique pure co-localisée (même motif que `ChatterTimeline.parseMarketingTouch`) :
// testable sans DOM, sans réseau. `body` (optionnel) : le corps de l'entrée, lu seulement par le filtre « Devis ».
export function matchesTimelineFilter(kind, filterKey, body) {
  switch (filterKey) {
    case 'notes': return kind === 'note'
    case 'appels': return kind === 'appel'
    case 'emails': return kind === 'email'
    case 'devis': return (typeof kind === 'string' && kind.startsWith('devis_')) || estActionClientSurDevis(kind, body)
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
    if (!a?.pinned && matchesTimelineFilter(a.kind, filterKey, a.body) && horo(a) > plusRecenteVisible) plusRecenteVisible = horo(a)
  }
  return entries.filter((a) => !matchesTimelineFilter(a.kind, filterKey, a.body) && horo(a) > plusRecenteVisible).length
}
