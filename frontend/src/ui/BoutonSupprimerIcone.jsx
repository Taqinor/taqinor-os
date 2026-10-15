import { Trash2 } from 'lucide-react'
import { IconButton } from './IconButton'

/* Bouton icône « corbeille » d'une ligne de liste (rouge destructif). Les
   props (`label`, `size`, `variant`, `onClick`, `disabled`…) vont à l'IconButton.
   Un seul endroit — jamais recopié écran par écran. */
export default function BoutonSupprimerIcone(props) {
  return (
    <IconButton className="text-destructive hover:text-destructive" {...props}>
      <Trash2 className="size-4" aria-hidden="true" />
    </IconButton>
  )
}
