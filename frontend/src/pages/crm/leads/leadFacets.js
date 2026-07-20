// LB52 — construction PURE des facettes de filtres actifs (chips
// « Dimension : valeur ✕ », patron Odoo web.SearchBar.Facets) : partagée par
// la rangée facettes desktop CONDITIONNELLE (LeadsPage — rend `null` à vide,
// patron Twenty ViewBarDetails/Linear) et le panneau Filtres mobile
// (FilterBar). Zéro React — testable `node --test`.
// Exclues : `q` (déjà dans l'input), `mesLeads` et `contact_preference`
// quand c'est le mode « ☎ Rappels » (portés par les QuickFilterChips), et
// `score` 'chaud' (chip « Chauds »).
import {
  EMPTY_FILTERS, PRIORITE_LABELS, STAGE_LABELS, TYPE_INSTALLATION_LABELS,
} from '../../../features/crm/stages'

export const RELANCE_LABELS = {
  aujourdhui: "Aujourd'hui",
  retard: 'En retard',
  semaine: 'Cette semaine',
}

export function buildLeadFacets(filters, canalOptions = []) {
  const facets = []
  if (filters.stage) facets.push({ key: 'stage', dim: 'Étape', label: STAGE_LABELS[filters.stage] ?? filters.stage })
  if (filters.type_installation) facets.push({ key: 'type_installation', dim: 'Marché', label: TYPE_INSTALLATION_LABELS[filters.type_installation] ?? filters.type_installation })
  if (filters.canal) facets.push({ key: 'canal', dim: 'Canal', label: canalOptions.find((o) => o.value === filters.canal)?.label ?? filters.canal })
  if (filters.contact_preference === 'whatsapp_only') facets.push({ key: 'contact_preference', dim: 'Contact', label: 'WhatsApp uniquement' })
  if (filters.owner) facets.push({ key: 'owner', dim: 'Responsable', label: filters.owner })
  if (filters.priorite) facets.push({ key: 'priorite', dim: 'Priorité', label: PRIORITE_LABELS[filters.priorite] ?? filters.priorite })
  if (filters.tag) facets.push({ key: 'tag', dim: 'Tag', label: filters.tag })
  // 'aujourdhui'/'retard' sont portés par les chips comptées ; seule
  // « Cette semaine » (panneau) mérite une facette.
  if (filters.relance === 'semaine') facets.push({ key: 'relance', dim: 'Relance', label: RELANCE_LABELS.semaine })
  if (filters.perdus !== EMPTY_FILTERS.perdus) facets.push({ key: 'perdus', dim: 'Perdus', label: filters.perdus === 'sans' ? 'Sans' : 'Seuls' })
  if ((filters.archived ?? 'actifs') !== EMPTY_FILTERS.archived) facets.push({ key: 'archived', dim: 'Archivés', label: filters.archived === 'tous' ? 'Inclus' : 'Seuls' })
  return facets
}

export default buildLeadFacets
