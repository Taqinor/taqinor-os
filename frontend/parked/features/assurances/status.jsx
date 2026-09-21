/* ============================================================================
   Constantes de statut/type du module Assurances (miroir des choix backend
   apps/assurances/models.py). Source unique des libellés et pastilles.
   ========================================================================== */

// PoliceAssurance.TypePolice
export const POLICE_TYPES = [
  { value: 'rc_pro', label: 'RC professionnelle' },
  { value: 'decennale', label: 'Décennale' },
  { value: 'multirisque', label: 'Multirisque' },
  { value: 'cyber', label: 'Cyber' },
  { value: 'homme_cle', label: 'Homme-clé' },
  { value: 'transport_marchandises', label: 'Transport de marchandises' },
  { value: 'bris_machine', label: 'Bris de machine' },
  { value: 'perte_exploitation', label: "Perte d'exploitation" },
  { value: 'autre', label: 'Autre' },
]

// PoliceAssurance.Statut
export const POLICE_STATUS = {
  active: { label: 'Active', tone: 'green' },
  suspendue: { label: 'Suspendue', tone: 'amber' },
  resiliee: { label: 'Résiliée', tone: 'slate' },
  expiree: { label: 'Expirée', tone: 'red' },
}

// DeclarationSinistre.Statut
export const SINISTRE_STATUS = {
  declare: { label: 'Déclaré', tone: 'blue' },
  en_expertise: { label: 'En expertise', tone: 'amber' },
  indemnise: { label: 'Indemnisé', tone: 'green' },
  refuse: { label: 'Refusé', tone: 'red' },
  clos: { label: 'Clos', tone: 'slate' },
}

// DeclarationSinistre.TypeSinistre
export const SINISTRE_TYPES = [
  { value: 'dommage_materiel', label: 'Dommage matériel' },
  { value: 'responsabilite_civile', label: 'Responsabilité civile' },
  { value: 'decennale', label: 'Décennale' },
  { value: 'cyber', label: 'Cyber' },
  { value: 'vol', label: 'Vol' },
  { value: 'incendie', label: 'Incendie' },
  { value: 'autre', label: 'Autre' },
]

/** Nombre de jours avant `dateEcheance` (négatif = déjà échu). */
export function joursAvant(dateEcheance) {
  if (!dateEcheance) return null
  const today = new Date()
  today.setHours(0, 0, 0, 0)
  const echeance = new Date(dateEcheance)
  echeance.setHours(0, 0, 0, 0)
  return Math.round((echeance - today) / (1000 * 60 * 60 * 24))
}

/** Ton de badge pour un badge d'échéance (rouge < 7 j, ambre < 30 j). */
export function toneEcheance(dateEcheance) {
  const j = joursAvant(dateEcheance)
  if (j == null) return 'slate'
  if (j < 0) return 'red'
  if (j < 7) return 'red'
  if (j < 30) return 'amber'
  return 'green'
}
