import { statusPill } from '../../ui/module'

/* ============================================================================
   NTIDE1/NTIDE5 — Taxonomie de statut d'une idée.
   ----------------------------------------------------------------------------
   Miroir 1:1 de ``Idee.Statut`` (backend, apps/innovation/models.py). Aucune
   valeur en dur ailleurs : pastille et transitions dérivent de cette carte.
   ========================================================================== */

export const STATUT_MAP = {
  ouvert: { label: 'Ouvert', tone: 'info' },
  examinee: { label: 'Examinée', tone: 'warning' },
  retenue: { label: 'Retenue', tone: 'success' },
  realisee: { label: 'Réalisée', tone: 'success' },
  fermee: { label: 'Fermée', tone: 'neutral' },
}

export const StatutIdeePill = statusPill(STATUT_MAP)

/** Transitions autorisées depuis un statut (miroir de la machine à états
 * ``apps.innovation.services._TRANSITIONS``). */
export function transitionsPour(statut) {
  switch (statut) {
    case 'ouvert':
      return ['examiner', 'fermer']
    case 'examinee':
      return ['retenir', 'fermer']
    case 'retenue':
      return ['realiser', 'fermer']
    default:
      return [] // realisee / fermee : terminaux
  }
}

/** True si le statut est terminal (aucune transition possible). */
export function estTerminal(statut) {
  return statut === 'realisee' || statut === 'fermee'
}

export const TRANSITION_LABELS = {
  examiner: 'Examiner',
  retenir: 'Retenir',
  realiser: 'Réaliser',
  fermer: 'Fermer',
}
