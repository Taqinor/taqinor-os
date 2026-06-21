import { forwardRef } from 'react'
import { Button } from './Button'

/**
 * G21 — Bouton icône carré. `label` OBLIGATOIRE (aria-label + title) car il n'y
 * a pas de texte visible. Réutilise les variantes de Button.
 *
 * N63 — Plancher d'accessibilité : si `label` manque, on retombe sur un
 * `aria-label` non vide ('Bouton') plutôt que de laisser un bouton icône SANS
 * nom accessible — un lecteur d'écran annoncerait alors « bouton » vide. Les
 * appels existants passent tous `label`, donc ce repli n'en change aucun.
 */
export const IconButton = forwardRef(function IconButton(
  { label, variant = 'ghost', size = 'icon', title, children, ...props },
  ref,
) {
  const accessibleLabel = label ?? props['aria-label'] ?? 'Bouton'
  // G125 — un bouton à icône seule DOIT être étiqueté. En dev, on signale
  // l'oubli (sans casser : le repli ci-dessus garantit un nom accessible).
  if (
    import.meta.env?.DEV &&
    label == null &&
    props['aria-label'] == null
  ) {
    console.warn(
      'IconButton: `label` (ou `aria-label`) est requis pour un bouton à icône seule ; repli sur « Bouton ».',
    )
  }
  return (
    <Button
      ref={ref}
      variant={variant}
      size={size}
      aria-label={accessibleLabel}
      title={title ?? accessibleLabel}
      {...props}
    >
      {children}
    </Button>
  )
})

export default IconButton
