import { statusPill } from '../../ui/module'

/* ============================================================================
   UX44 — Taxonomies de statut & gravité d'une réclamation / litige.
   ----------------------------------------------------------------------------
   Miroirs 1:1 de ``Reclamation.Statut`` et ``Reclamation.Gravite`` (backend).
   Aucune valeur en dur ailleurs : pastilles et helpers dérivent de ces cartes.
   ========================================================================== */

export const STATUT_MAP = {
  ouverte: { label: 'Ouverte', tone: 'info' },
  en_traitement: { label: 'En traitement', tone: 'warning' },
  resolue: { label: 'Résolue', tone: 'success' },
  rejetee: { label: 'Rejetée', tone: 'danger' },
}

export const GRAVITE_MAP = {
  faible: { label: 'Faible', tone: 'neutral' },
  moyenne: { label: 'Moyenne', tone: 'warning' },
  elevee: { label: 'Élevée', tone: 'danger' },
}

export const TYPE_MAP = {
  financier: 'Financier',
  qualite: 'Qualité',
  delai: 'Délai',
  commercial: 'Commercial',
  autre: 'Autre',
}

export const StatutReclamationPill = statusPill(STATUT_MAP)
export const GraviteReclamationPill = statusPill(GRAVITE_MAP)

/** Transitions autorisées depuis un statut (miroir de la machine à états). */
export function transitionsPour(statut) {
  switch (statut) {
    case 'ouverte':
      return ['prendre_en_charge', 'rejeter']
    case 'en_traitement':
      return ['resoudre', 'rejeter']
    default:
      return [] // resolue / rejetee : terminaux
  }
}

/** True si le statut est terminal (aucune transition possible). */
export function estTerminal(statut) {
  return statut === 'resolue' || statut === 'rejetee'
}
