/* ============================================================================
   NTCRD23 — Pastille d'état crédit (vert/orange/rouge) à afficher à côté du nom
   client dans DevisList / VentesKanban. Lecture seule ; la couleur vient du
   batch `creditApi.getBadges()` (endpoint léger, cache court côté sélecteur).
   Un client en blocage ressort visuellement sans ouvrir la fiche.

   WIR189 — la couleur est portée par des classes utilitaires (jetons
   sémantiques success/warning/destructive), jamais par une feuille de style
   absente : avant, `credit-badge--<couleur>` n'existait dans aucun CSS, donc la
   pastille se rendait invisible même quand la donnée était là.
   ========================================================================== */

const LABELS = {
  vert: 'Crédit OK',
  orange: 'Crédit à surveiller',
  rouge: 'Crédit bloqué',
}

// Les 3 couleurs servies par `credit.selectors.badge_credit`. Une valeur
// inconnue ne rend RIEN (jamais une pastille grise trompeuse).
const TONS = {
  vert: 'border-success/50 bg-success',
  orange: 'border-warning/50 bg-warning',
  rouge: 'border-destructive/50 bg-destructive',
}

export default function CreditBadge({ couleur }) {
  const ton = TONS[couleur]
  if (!ton) return null
  return (
    <span
      className={`credit-badge credit-badge--${couleur} inline-block size-2.5 shrink-0 rounded-full border align-middle ${ton}`}
      title={LABELS[couleur]}
      aria-label={LABELS[couleur]}
      data-credit-badge={couleur}
      data-testid="credit-badge"
    />
  )
}
