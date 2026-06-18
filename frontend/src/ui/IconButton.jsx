import { forwardRef } from 'react'
import { Button } from './Button'

/**
 * G21 — Bouton icône carré. `label` OBLIGATOIRE (aria-label + title) car il n'y
 * a pas de texte visible. Réutilise les variantes de Button.
 */
export const IconButton = forwardRef(function IconButton(
  { label, variant = 'ghost', size = 'icon', title, children, ...props },
  ref,
) {
  return (
    <Button
      ref={ref}
      variant={variant}
      size={size}
      aria-label={label}
      title={title ?? label}
      {...props}
    >
      {children}
    </Button>
  )
})

export default IconButton
