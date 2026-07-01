import { statusPill } from '../../ui/module'

/* ============================================================================
   RH — Taxonomies de statut (pastilles) & libellés partagés.
   ----------------------------------------------------------------------------
   Un seul endroit pour les mappings valeur → { label, tone } utilisés par les
   colonnes de tableau, les filtres et les en-têtes de détail du module RH.
   Les valeurs correspondent aux `choices` des modèles Django (apps.rh).
   ========================================================================== */

// Statut d'un dossier employé.
export const StatutEmploye = statusPill({
  actif: { label: 'Actif', tone: 'success' },
  suspendu: { label: 'Suspendu', tone: 'warning' },
  sorti: { label: 'Sorti', tone: 'neutral' },
})

// Type de contrat.
export const TYPE_CONTRAT_LABELS = {
  cdi: 'CDI',
  cdd: 'CDD',
  interim: 'Intérim',
  stage: 'Stage',
  anapec: 'ANAPEC',
  freelance: 'Freelance',
}

// Statut d'une demande de congé (workflow brouillon→soumise→validée/refusée).
export const StatutConge = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  soumise: { label: 'Soumise', tone: 'info' },
  validee: { label: 'Validée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Statut d'une note de frais.
export const StatutNoteFrais = statusPill({
  soumise: { label: 'Soumise', tone: 'info' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
  remboursee: { label: 'Remboursée', tone: 'success' },
})

// Statut d'une avance sur salaire.
export const StatutAvance = statusPill({
  demandee: { label: 'Demandée', tone: 'info' },
  approuvee: { label: 'Approuvée', tone: 'success' },
  refusee: { label: 'Refusée', tone: 'danger' },
  deduite: { label: 'Déduite', tone: 'neutral' },
})

// Étape d'une candidature (pipeline ATS léger).
export const EtapeCandidature = statusPill({
  recu: { label: 'Reçu', tone: 'neutral' },
  preselection: { label: 'Présélection', tone: 'info' },
  entretien: { label: 'Entretien', tone: 'info' },
  offre: { label: 'Offre', tone: 'warning' },
  embauche: { label: 'Embauché', tone: 'success' },
  rejete: { label: 'Rejeté', tone: 'danger' },
})

// Statut d'une ouverture de poste.
export const StatutPoste = statusPill({
  ouvert: { label: 'Ouvert', tone: 'success' },
  pourvu: { label: 'Pourvu', tone: 'neutral' },
  clos: { label: 'Clos', tone: 'neutral' },
  annule: { label: 'Annulé', tone: 'neutral' },
})

// Gravité d'un accident du travail.
export const GraviteAccident = statusPill({
  leger: { label: 'Léger', tone: 'warning' },
  grave: { label: 'Grave', tone: 'danger' },
  mortel: { label: 'Mortel', tone: 'danger' },
})

// Statut d'un accident (déclaré / traité / clos).
export const StatutAccident = statusPill({
  declare: { label: 'Déclaré', tone: 'info' },
  traite: { label: 'Traité', tone: 'warning' },
  clos: { label: 'Clos', tone: 'neutral' },
})

// Statut d'une sanction disciplinaire.
export const StatutSanction = statusPill({
  notifiee: { label: 'Notifiée', tone: 'warning' },
  contestee: { label: 'Contestée', tone: 'danger' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Statut d'un ordre de mission.
export const StatutMission = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  emis: { label: 'Émis', tone: 'info' },
  cloture: { label: 'Clôturé', tone: 'success' },
})

// Statut d'une session de formation.
export const StatutSession = statusPill({
  planifiee: { label: 'Planifiée', tone: 'info' },
  realisee: { label: 'Réalisée', tone: 'success' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

// Statut d'une analyse de risques chantier.
export const StatutAnalyse = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  validee: { label: 'Validée', tone: 'success' },
  cloturee: { label: 'Clôturée', tone: 'neutral' },
})

// Statut d'une évaluation employé.
export const StatutEvaluation = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  validee: { label: 'Validée', tone: 'success' },
  cloturee: { label: 'Clôturée', tone: 'neutral' },
})

// Libellé du type d'échéance RH (moteur unifié FG175).
export const ECHEANCE_TYPE_LABELS = {
  habilitation: 'Habilitation',
  certification: 'Certification',
  document: 'Document',
  visite_medicale: 'Visite médicale',
  dotation_epi: 'Renouvellement EPI',
  epi_peremption: 'Péremption EPI',
  epi_controle: 'Contrôle EPI',
}
