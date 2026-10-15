import { Button } from './Button'

/* Pied d'un popover de saisie : « Annuler » (outline, petit) puis le bouton
   de validation en enfant. `className` : rangée de boutons propre au popover. */
export default function PiedPopover({ className, onAnnuler, children }) {
  return (
    <div className={className}>
      <Button type="button" variant="outline" size="sm" onClick={onAnnuler}>
        Annuler
      </Button>
      {children}
    </div>
  )
}
