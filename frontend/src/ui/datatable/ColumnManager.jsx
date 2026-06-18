import { SlidersHorizontal, Eye, EyeOff, RotateCcw } from 'lucide-react'
import { Button } from '../Button'
import {
  DropdownMenu, DropdownMenuTrigger, DropdownMenuContent,
  DropdownMenuLabel, DropdownMenuSeparator, DropdownMenuCheckboxItem, DropdownMenuItem,
} from '../DropdownMenu'

/* ============================================================================
   H31 — Gestion des colonnes : afficher/masquer (cases à cocher) + réinitialiser.
   Le réordonnancement se fait par glisser-déposer sur les en-têtes (HTML5 drag,
   sans dépendance) ; l'épinglage via le menu d'en-tête. Pilote `columnState`
   par dispatch du réducteur pur (logic.js).
   `columns` = définitions complètes ; `columnState` = état courant.
   ========================================================================== */
export function ColumnManager({ columns, columnState, dispatch }) {
  const hideableCount = columns.filter((c) => c.hideable !== false).length
  const visibleCount = columns.filter((c) => c.hideable !== false && !columnState.hidden[c.id]).length

  return (
    <DropdownMenu>
      <DropdownMenuTrigger asChild>
        <Button variant="outline" size="sm">
          <SlidersHorizontal />
          <span className="hidden sm:inline">Colonnes</span>
          <span className="text-muted-foreground">
            {visibleCount}/{hideableCount}
          </span>
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="max-h-80 overflow-y-auto">
        <DropdownMenuLabel>Colonnes visibles</DropdownMenuLabel>
        {columns.map((c) => {
          if (c.hideable === false) return null
          const visible = !columnState.hidden[c.id]
          return (
            <DropdownMenuCheckboxItem
              key={c.id}
              checked={visible}
              onSelect={(e) => e.preventDefault()}
              onCheckedChange={() => dispatch({ type: 'toggleVisibility', id: c.id })}
            >
              {visible ? <Eye className="size-3.5 text-muted-foreground" /> : <EyeOff className="size-3.5 text-muted-foreground" />}
              {c.header ?? c.id}
            </DropdownMenuCheckboxItem>
          )
        })}
        <DropdownMenuSeparator />
        <DropdownMenuItem onSelect={() => dispatch({ type: 'reset', columns })}>
          <RotateCcw /> Réinitialiser les colonnes
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  )
}

export default ColumnManager
