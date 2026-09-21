// Statuts locaux du module Location (miroir backend OrdreLocation) — extraits
// de LocationPage.jsx pour respecter react-refresh (un fichier composant
// n'exporte que des composants) tout en restant testables.
import { statusPill } from '../../ui/module'

export const StatutLocation = statusPill({
  reservee: { label: 'Réservée', tone: 'info' },
  enlevee: { label: 'Enlevée', tone: 'success' },
  retournee: { label: 'Retournée', tone: 'warning' },
  cloturee: { label: 'Clôturée', tone: 'neutral' },
  annulee: { label: 'Annulée', tone: 'neutral' },
})

export const StatutCautionLocation = statusPill({
  aucune: { label: 'Aucune', tone: 'neutral' },
  encaissee: { label: 'Encaissée', tone: 'success' },
  restituee: { label: 'Restituée', tone: 'neutral' },
  retenue_partielle: { label: 'Retenue', tone: 'warning' },
})
