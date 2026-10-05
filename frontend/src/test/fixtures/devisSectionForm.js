// ACAL345 — formulaire de base « Paramètres › Devis » partagé par les tests
// de DevisSection (ci, pompage) au lieu d'être recopié.
import { formReglagesPompage } from '../../pages/parametres/peConstants'

export const formDevisBase = (extra = {}) => ({
  payment_terms: {}, doc_prefixes: {}, doc_numbering: {},
  quote_validity_days: 30, agricole_pump_hours: 7,
  delai_visite_technique: '', delai_installation: '',
  commission_mode: 'off', commission_valeur: '',
  dgi_export_actif: false, tva_standard: 20, tva_panneaux: 10,
  ...formReglagesPompage({}),
  ...extra,
})
