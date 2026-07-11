import { forwardRef } from 'react'
import * as ProgressPrimitive from '@radix-ui/react-progress'
import { cn } from '../lib/cn'
import { pressCurve } from './interaction'

/* G29 — Barre de progression (0–100). `tone` colore la barre.
   VX126 — courbe alignée sur Button (`pressCurve`) au lieu du défaut Tailwind
   `150ms ease` linéaire-ish, pour un mouvement cohérent avec le reste des
   primitifs animés (Switch, Button). */
const TONE = {
  primary: 'bg-primary',
  success: 'bg-success',
  warning: 'bg-warning',
  danger: 'bg-destructive',
  info: 'bg-info',
}

export const Progress = forwardRef(function Progress(
  { className, value = 0, tone = 'primary', ...props },
  ref,
) {
  const pct = Math.max(0, Math.min(100, Number(value) || 0))
  return (
    <ProgressPrimitive.Root
      ref={ref}
      value={pct}
      className={cn('relative h-2 w-full overflow-hidden rounded-full bg-muted', className)}
      {...props}
    >
      <ProgressPrimitive.Indicator
        className={cn('h-full w-full flex-1 transition-transform', pressCurve, TONE[tone] ?? TONE.primary)}
        style={{ transform: `translateX(-${100 - pct}%)` }}
      />
    </ProgressPrimitive.Root>
  )
})

export default Progress
