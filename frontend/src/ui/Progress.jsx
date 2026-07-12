import { forwardRef } from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn } from '../lib/cn'
import { pressCurve } from './interaction'

/* G29 — Barre de progression (0–100). `tone` colore la barre.
   VX126 — courbe alignée sur Button (`pressCurve`) au lieu du défaut Tailwind
   `150ms ease` linéaire-ish, pour un mouvement cohérent avec le reste des
   primitifs animés (Switch, Button).
   VX129 — `indeterminate` : jusqu'ici SEUL état possible = une barre figée à
   0 % pendant une attente de durée inconnue. Une barre balaie la piste en
   boucle (`--animate-progress-sweep`, tokens.css) ; se fige automatiquement
   sous reduced-motion via le garde global `*` d'index.css. */
const TONE = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-destructive',
  info: 'bg-info',
}

export const Progress = forwardRef(function Progress(
  { className, value = 0, tone = 'primary', indeterminate = false, ...props },
  ref,
) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <ProgressPrimitive.Root
      ref={ref}
      value={indeterminate ? null : pct}
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn(
          'h-full flex-1',
          indeterminate ? 'w-1/3 animate-progress-sweep' : 'w-full transition-transform',
          !indeterminate && pressCurve,
          TONE[tone] ?? TONE.primary,
        )}
        style={indeterminate ? undefined : { transform: `translateX(-${100 - pct}%)` }}
      />
    </ProgressPrimitive.Root>
  )
})

export default Progress
