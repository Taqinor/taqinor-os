import { statusPill } from '../../ui/module'

/* ============================================================================
   Taxonomies de statut du module Contrats (UX34–UX37).
   ----------------------------------------------------------------------------
   Une fabrique `statusPill(map)` par entité ; chaque map reflète EXACTEMENT les
   `TextChoices` du backend (`apps/contrats/models.py`). Aucune valeur inventée.
   Les tons suivent la convention UX1 : neutral / info / success / warning /
   danger. Pas de JSX ici — uniquement des composants Pill exportés.
   ========================================================================== */

// Contrat — machine d'états gardée (CONTRAT12).
// brouillon→approbation→signé→actif→suspendu→résilié→expiré.
export const CONTRAT_STATUS = {
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  en_approbation: { label: 'En approbation', tone: 'info' },
  signe: { label: 'Signé', tone: 'info' },
  actif: { label: 'Actif', tone: 'success' },
  suspendu: { label: 'Suspendu', tone: 'warning' },
  resilie: { label: 'Résilié', tone: 'danger' },
  expire: { label: 'Expiré', tone: 'warning' },
}
export const StatutContrat = statusPill(CONTRAT_STATUS)

// Ordre canonique de la machine d'états (affichage du graphe lisible).
export const CONTRAT_STATUS_ORDER = [
  'brouillon',
  'en_approbation',
  'signe',
  'actif',
  'suspendu',
  'resilie',
  'expire',
]

// Types de contrat (Contrat.TypeContrat) — pour les filtres/segments.
export const CONTRAT_TYPES = [
  { value: 'vente', label: 'Vente' },
  { value: 'om', label: 'O&M' },
  { value: 'monitoring', label: 'Monitoring' },
  { value: 'garantie', label: 'Garantie' },
  { value: 'ppa', label: 'PPA' },
  { value: 'fournisseur', label: 'Fournisseur' },
  { value: 'sous_traitance', label: 'Sous-traitance' },
  { value: 'location', label: 'Location' },
  { value: 'emploi', label: 'Emploi' },
  { value: 'nda', label: 'NDA' },
  { value: 'maintenance', label: 'Maintenance' },
  { value: 'autre', label: 'Autre' },
]

// Niveaux de confidentialité (Contrat.NiveauConfidentialite — CONTRAT6).
export const StatutConfidentialite = statusPill({
  public: { label: 'Public', tone: 'neutral' },
  interne: { label: 'Interne', tone: 'info' },
  confidentiel: { label: 'Confidentiel', tone: 'danger' },
})

// Alerte (AlerteContrat.Statut — CONTRAT22).
export const StatutAlerte = statusPill({
  planifiee: { label: 'Planifiée', tone: 'info' },
  envoyee: { label: 'Envoyée', tone: 'success' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Jalon (JalonContrat.Statut — CONTRAT26).
export const StatutJalon = statusPill({
  a_venir: { label: 'À venir', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  atteint: { label: 'Atteint', tone: 'success' },
  en_retard: { label: 'En retard', tone: 'danger' },
  annule: { label: 'Annulé', tone: 'neutral' },
})

// Obligation (Obligation.Statut — CONTRAT26).
export const StatutObligation = statusPill({
  a_faire: { label: 'À faire', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'info' },
  faite: { label: 'Réalisée', tone: 'success' },
  en_retard: { label: 'En retard', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Résiliation (Resiliation.Statut — CONTRAT25).
export const StatutResiliation = statusPill({
  demande: { label: 'Demandée', tone: 'warning' },
  effective: { label: 'Effective', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Retenue de garantie (RetenueGarantie.Statut — CONTRAT28).
export const StatutRetenue = statusPill({
  retenue: { label: 'Retenue', tone: 'warning' },
  liberee: { label: 'Libérée', tone: 'success' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Caution (Caution.Statut — CONTRAT29).
export const StatutCaution = statusPill({
  active: { label: 'Active', tone: 'success' },
  mainlevee: { label: 'Mainlevée', tone: 'neutral' },
  appelee: { label: 'Appelée', tone: 'danger' },
  expiree: { label: 'Expirée', tone: 'warning' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Échéancier (EcheancierContrat.Statut — CONTRAT30).
export const StatutEcheancier = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  actif: { label: 'Actif', tone: 'success' },
  solde: { label: 'Soldé', tone: 'info' },
  annule: { label: 'Annulé', tone: 'neutral' },
})

// Ligne d'échéance (LigneEcheance.Statut — CONTRAT30).
export const StatutLigneEcheance = statusPill({
  a_venir: { label: 'À venir', tone: 'neutral' },
  payee: { label: 'Payée', tone: 'success' },
  en_retard: { label: 'En retard', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Pièce de conformité (PieceConformite.Statut — CONTRAT34).
export const StatutPiece = statusPill({
  manquante: { label: 'Manquante', tone: 'danger' },
  fournie: { label: 'Fournie', tone: 'info' },
  validee: { label: 'Validée', tone: 'success' },
  expiree: { label: 'Expirée', tone: 'warning' },
  refusee: { label: 'Refusée', tone: 'danger' },
})
