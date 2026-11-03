import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent } from './DropdownMenu'

// ENF19 — le menu « Plus d'actions » d'une ligne de liste, UNE fois : le bouton
// `declencheur` (propre à chaque écran) et ses entrées, alignées à droite.
export default function MenuActionsLigne({ declencheur, children }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{declencheur}</DropdownMenuTrigger>
      <DropdownMenuContent align="end">{children}</DropdownMenuContent>
    </DropdownMenu>
  )
}
