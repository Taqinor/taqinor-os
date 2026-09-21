import { statusPill } from '../../ui/module'

/* ============================================================================
   MAGASIN — pastilles de statut (put-away / pick-list / colis).
   ----------------------------------------------------------------------------
   Fabriquées via `statusPill` (kit module-shell, UX1) — même pattern que
   `flotte/statusPills.jsx`.
   ========================================================================== */

export const PutAwayStatutPill = statusPill({
  a_ranger: { label: 'À ranger', tone: 'warning' },
  range: { label: 'Rangé', tone: 'success' },
})

export const PickListStatutPill = statusPill({
  emis: { label: 'Émis', tone: 'neutral' },
  en_cours: { label: 'En cours', tone: 'warning' },
  termine: { label: 'Terminé', tone: 'success' },
})

export const ColisStatutPill = statusPill({
  preparation: { label: 'En préparation', tone: 'neutral' },
  controle: { label: 'Contrôlé', tone: 'warning' },
  expedie: { label: 'Expédié', tone: 'success' },
})
