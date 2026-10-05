// SPL211 — aides partagées entre FactureList.jsx et factureList/FactureRow.jsx
// (déplacées VERBATIM ; `today` reste évalué au chargement du module).
import { toNumber } from '../../../lib/format'

// Facture à solde partiel : un acompte encaissé mais reste dû > 0.
export const isPartiallyPaid = f =>
  toNumber(f.montant_paye) > 0 && toNumber(f.montant_du) > 0 &&
  f.statut !== 'annulee'

export const today = new Date().toISOString().slice(0, 10)
// ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER — une facture au STATUT « en_retard »
// (même sans échéance) est affichée « En retard » : elle doit aussi tomber dans
// l'onglet « En retard » (sinon 4 lignes « En retard » et un onglet vide).
export const isOverdue = f =>
  f.is_overdue ||
  f.statut === 'en_retard' ||
  (f.statut === 'emise' && f.date_echeance && f.date_echeance < today)

// ERR-QAH-VENTES-FACTURES-KPI-ENCAISSER — « Reste à encaisser » ne compte que
// les factures VIVANTES : ni brouillon (pas encore émise), ni annulée, ni payée.
export const STATUTS_HORS_ENCAISSEMENT = ['brouillon', 'annulee', 'payee']
