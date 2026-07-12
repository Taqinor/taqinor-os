import { X } from 'lucide-react'
import { cn } from '../lib/cn'

/* G29 — Tag / Chip (étiquette, optionnellement supprimable). */
export function Tag({ children, onRemove, className, ...props }) {
  return (
    <span
      className={cn(
        'inline-flex items-center gap-1 rounded-md border border-border bg-secondary px-2 py-0.5',
        'text-xs font-medium text-secondary-foreground',
        className,
      )}
      {...props}
    >
      {children}
      {onRemove && (
        <button
          type="button"
          onClick={onRemove}
          aria-label="Retirer"
          className="-mr-0.5 rounded-sm text-muted-foreground hover:text-foreground focus-ring"
        >
          <X className="size-3" />
        </button>
      )}
    </span>
  )
}

export default Tag
