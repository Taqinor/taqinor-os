import { forwardRef } from 'react'
import { cn } from '../lib/cn'

/* G22 — Zone de texte multi-ligne (16px mobile anti-zoom).
   VX124 — caret-primary : curseur de saisie teinté marque (voir Input.jsx).
   VX127 — `readOnly` ≠ `disabled` (voir Input.jsx) : fond distinct, curseur
   par défaut, texte pleine opacité et toujours sélectionnable/copiable. */
export const Textarea = forwardRef(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-foreground shadow-ui-xs',
        'transition-colors placeholder:text-muted-foreground caret-primary',
        'focus-ring focus-visible:border-ring',
        'disabled:cursor-not-allowed disabled:opacity-60',
        'read-only:cursor-default read-only:bg-muted/40 read-only:opacity-100',
        'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
        'text-base sm:text-sm',
        className,
      )}
      {...props}
    />
  )
})

export default Textarea
