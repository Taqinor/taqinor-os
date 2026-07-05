// ZFAC9 — Vue kanban des factures par statut (pipeline visuel).
//
// Helpers PURS (aucune dépendance React) reproduisant EXACTEMENT la même
// dérivation de colonne que les onglets existants de `FactureList.jsx`
// (`statut` du modèle + `isOverdue`/`isPartiallyPaid` calculés côté client
// sur `montant_paye`/`montant_du`, sans nouveau champ backend) — priorité
// identique à `counts`/`statutKey` dans FactureList.jsx : une facture émise
// en retard tombe dans « En retard », jamais dans « Émise » ET « En retard »
// à la fois (une seule colonne par facture, comme un seul onglet).
import { toNumber } from '../../lib/format.js'

export const KANBAN_COLUMNS = [
  { key: 'brouillon', label: 'Brouillon' },
  { key: 'emise', label: 'Émise' },
  { key: 'en_retard', label: 'En retard' },
  { key: 'partielle', label: 'Partiellement payée' },
  { key: 'payee', label: 'Payée' },
]

// Facture à solde partiel : un acompte encaissé mais reste dû > 0 (miroir de
// `isPartiallyPaid` dans FactureList.jsx).
export function isPartiallyPaid(f) {
  return toNumber(f?.montant_paye) > 0 && toNumber(f?.montant_du) > 0 && f?.statut !== 'annulee'
}

// Miroir de `isOverdue` dans FactureList.jsx — `today` est injecté (pas
// `new Date()` local) pour rester déterministe en test.
export function isOverdue(f, today) {
  return !!(f?.is_overdue
    || (f?.statut === 'emise' && f?.date_echeance && f.date_echeance < today))
}

// Colonne kanban d'UNE facture — même priorité que les onglets : brouillon,
// puis en_retard (émise + en retard), puis émise, puis partielle, puis
// payée. `annulee` n'a délibérément AUCUNE colonne (comme l'onglet
// « Annulées » existant reste une vue à part, jamais affichée dans le
// pipeline visuel qui ne montre que le flux actif) — une facture annulée est
// omise du kanban plutôt que forcée dans une colonne trompeuse.
export function columnForFacture(f, today) {
  if (!f) return null
  if (f.statut === 'annulee') return null
  if (f.statut === 'brouillon') return 'brouillon'
  if (isOverdue(f, today)) return 'en_retard'
  if (f.statut === 'emise') return 'emise'
  if (isPartiallyPaid(f)) return 'partielle'
  if (f.statut === 'payee') return 'payee'
  return null
}

// Regroupe une liste de factures par colonne kanban. Renvoie un objet
// { [columnKey]: Facture[] } avec TOUTES les clés de KANBAN_COLUMNS
// présentes (même vides) pour un rendu stable colonne par colonne.
export function groupByColumn(factures, today = new Date().toISOString().slice(0, 10)) {
  const groups = Object.fromEntries(KANBAN_COLUMNS.map((c) => [c.key, []]))
  for (const f of (factures || [])) {
    const col = columnForFacture(f, today)
    if (col && groups[col]) groups[col].push(f)
  }
  return groups
}

// Total TTC d'une colonne — `total_ttc` est le champ déjà rendu par
// FactureList.jsx (`f.total_ttc != null ? formatMAD(f.total_ttc) : '—'`).
export function columnTotal(factures) {
  return (factures || []).reduce((sum, f) => sum + (toNumber(f.total_ttc) || 0), 0)
}

// Résumé complet (compte + total) par colonne, prêt à rendre.
export function kanbanSummary(factures, today) {
  const groups = groupByColumn(factures, today)
  return KANBAN_COLUMNS.map((c) => ({
    ...c,
    factures: groups[c.key],
    count: groups[c.key].length,
    total: columnTotal(groups[c.key]),
  }))
}
