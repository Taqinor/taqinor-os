import { statusPill } from '../../ui/module'

/* ============================================================================
   NTIDE1/NTIDE4 — Taxonomie de statut d'une idée.
   ----------------------------------------------------------------------------
   Miroir 1:1 de ``Idee.Statut`` (backend, apps/innovation/models.py). Aucune
   valeur en dur ailleurs : pastille et filtres dérivent de cette carte.
   ========================================================================== */

export const STATUT_MAP = {
  ouvert: { label: 'Ouvert', tone: 'info' },
  examinee: { label: 'Examinée', tone: 'warning' },
  retenue: { label: 'Retenue', tone: 'success' },
  realisee: { label: 'Réalisée', tone: 'success' },
  fermee: { label: 'Fermée', tone: 'neutral' },
}

export const StatutIdeePill = statusPill(STATUT_MAP)
