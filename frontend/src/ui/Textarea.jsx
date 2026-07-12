import { forwardRef } from 'react'
import { cn } from '../lib/cn'
import { SANITIZE_PRESETS } from './Input'

/* G22 — Zone de texte multi-ligne (16px mobile anti-zoom).
   VX124 — caret-primary : curseur de saisie teinté marque (voir Input.jsx).
   VX174 — même prop `sanitize` que Input.jsx (source unique SANITIZE_PRESETS). */
export const Textarea = forwardRef(function Textarea({ className, invalid, sanitize, ...props }, ref) {
  const sanitizeProps = sanitize ? SANITIZE_PRESETS[sanitize] : null
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      {...sanitizeProps}
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-foreground shadow-ui-xs',
        'transition-colors placeholder:text-muted-foreground caret-primary',
        'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring',
        'disabled:cursor-not-allowed disabled:opacity-60',
        'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
        'text-base sm:text-sm',
        className,
      )}
      {...props}
    />
  )
})

export default Textarea
