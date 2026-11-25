import { DropdownMenu, DropdownMenuTrigger, DropdownMenuContent } from './DropdownMenu'

// ENF19 — le menu « Plus d'actions » d'une ligne de liste, UNE fois : le bouton
// `declencheur` (propre à chaque écran) et ses entrées, alignées à droite.
// T4-X6-005 — 17 actions sur la liste des devis dépassaient le haut de la
// fenêtre : marge de collision, hauteur bornée à la place que Radix mesure
// (`--radix-dropdown-menu-content-available-height`) et défilement interne.
export default function MenuActionsLigne({ declencheur, children }) {
  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>{declencheur}</DropdownMenuTrigger>
      <DropdownMenuContent align="end" collisionPadding={8}
        className="max-h-[var(--radix-dropdown-menu-content-available-height)] overflow-y-auto">
        {children}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
