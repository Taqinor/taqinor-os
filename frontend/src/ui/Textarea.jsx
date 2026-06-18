import { forwardRef } from 'react'
import { cn } from '../lib/cn'

/* G22 — Zone de texte multi-ligne (16px mobile anti-zoom). */
export const Textarea = forwardRef(function Textarea({ className, invalid, ...props }, ref) {
  return (
    <textarea
      ref={ref}
      aria-invalid={invalid || undefined}
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-foreground shadow-ui-xs',
        'transition-colors placeholder:text-muted-foreground',
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
