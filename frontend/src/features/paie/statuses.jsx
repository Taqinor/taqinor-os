import { statusPill } from '../../ui/module'

/* Pastilles de statut de la Paie (miroir des choix serveur, apps/paie/models.py). */

export const StatutPeriode = statusPill({
  brouillon: { label: 'Brouillon', tone: 'neutral' },
  calculee: { label: 'Calculée', tone: 'info' },
  validee: { label: 'Validée', tone: 'success' },
  cloturee: { label: 'Clôturée', tone: 'neutral' },
})

export const StatutBulletin = statusPill({
  brouillon: { label: 'Brouillon', tone: 'warning' },
  valide: { label: 'Validé', tone: 'success' },
})

export const StatutOrdre = statusPill({
  brouillon: { label: 'Brouillon', tone: 'warning' },
  emis: { label: 'Émis', tone: 'success' },
})
