/* ============================================================================
   NTCRD23 — Pastille d'état crédit (vert/orange/rouge) à afficher à côté du nom
   client dans DevisList / VentesKanban. Lecture seule ; la couleur vient du
   batch `creditApi.getBadges()` (endpoint léger, cache court côté sélecteur).
   Un client en blocage ressort visuellement sans ouvrir la fiche.
   ========================================================================== */

const LABELS = {
  vert: 'Crédit OK',
  orange: 'Crédit à surveiller',
  rouge: 'Crédit bloqué',
}

export default function CreditBadge({ couleur }) {
  if (!couleur) return null
  return (
    <span
      className={`credit-badge credit-badge--${couleur}`}
      title={LABELS[couleur] || ''}
      aria-label={LABELS[couleur] || ''}
      data-testid="credit-badge"
    />
  )
}
