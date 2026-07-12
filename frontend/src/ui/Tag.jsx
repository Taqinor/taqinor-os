import { X } from 'lucide-react'
import { cn } from '../lib/cn'

/* G29 — Tag / Chip (étiquette, optionnellement supprimable).
   VX129 — grammaire de chip UNIQUE : `tagBase`/`tagRemoveBase` exportés pour
   que tout autre jeton du repo (ex. MultiSelect, qui ne peut pas rendre ce
   composant tel quel — son bouton retirer vivrait dans un <button> parent
   imbriqué, invalide en HTML) consomme le MÊME rayon/hauteur/padding au lieu
   d'une 4ᵉ grammaire divergente (`rounded` nu + padding différent). */
export const tagBase =
  'inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5 ' +
  'text-xs font-medium text-secondary-foreground'
export const tagRemoveBase = '-mr-0.5 rounded-sm text-muted-foreground hover:text-foreground focus-ring'

export function Tag({ children, onRemove, className, ...props }) {
  return (
    <span className={cn(tagBase, className)} {...props}>
      {children}
      {onRemove && (
        <button type="button" onClick={onRemove} aria-label="Retirer" className={tagRemoveBase}>
          <X className="size-3" />
        </button>
      )}
    </span>
  )
}

export default Tag
