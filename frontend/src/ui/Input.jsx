import { forwardRef } from 'react'
import { cn } from '../lib/cn'

/* G22 — Champ texte. 16px sur mobile (anti-zoom iOS) → text-base sm:text-sm.
   `invalid` câble aria-invalid + style. `leading`/`trailing` = ornements
   (icône, unité). Hauteur pilotée par la densité (F20).
   VX124 — `caret-color: var(--primary)` : le curseur de saisie prend la
   teinte de marque au lieu du noir système, sur le champ le plus regardé
   de l'ERP (générateur de devis). */
const baseField =
  'flex w-full rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'transition-colors placeholder:text-muted-foreground caret-primary ' +
  'focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30 ' +
  'text-base sm:text-sm'

export const Input = forwardRef(function Input(
  { className, type = 'text', invalid, leading, trailing, ...props },
  ref,
) {
  const field = (
    <input
      ref={ref}
      type={type}
      aria-invalid={invalid || undefined}
      className={cn(
        baseField,
        'h-[var(--control-h)] px-[var(--control-px)] py-0',
        leading && 'pl-9',
        trailing && 'pr-12',
        className,
      )}
      {...props}
    />
  )
  if (!leading && !trailing) return field
  return (
    <div className="relative w-full">
      {leading && (
        <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-muted-foreground [&_svg]:size-4">
          {leading}
        </span>
      )}
      {field}
      {trailing && (
        <span className="pointer-events-none absolute inset-y-0 right-0 flex items-center pr-3 text-sm text-muted-foreground">
          {trailing}
        </span>
      )}
    </div>
  )
})

export default Input
