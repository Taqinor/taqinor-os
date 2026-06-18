import { cn } from '../lib/cn'
import { Card } from './Card'

/* G29 — Carte de KPI / statistique. `value` déjà formatée (via lib/format).
   `delta` optionnel : { value, direction: 'up'|'down', tone? }. Chiffres
   tabulaires pour alignement. */
export function Stat({ label, value, hint, delta, icon, className, ...props }) {
  const Icon = icon
  const deltaTone =
    delta?.tone ??
    (delta?.direction === 'up' ? 'success' : delta?.direction === 'down' ? 'danger' : 'muted')
  const deltaClass = {
    success: 'text-success',
    danger: 'text-destructive',
    muted: 'text-muted-foreground',
  }[deltaTone]

  return (
    <Card className={cn('p-4 sm:p-5', className)} {...props}>
      <div className="flex items-start justify-between gap-3">
        <span className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
          {label}
        </span>
        {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
      </div>
      <div className="mt-2 font-display text-2xl font-semibold tabular-nums leading-none">
        {value}
      </div>
      {(hint || delta) && (
        <div className="mt-1.5 flex items-center gap-2 text-xs">
          {delta && (
            <span className={cn('font-medium tabular-nums', deltaClass)}>
              {delta.direction === 'up' ? '▲' : delta.direction === 'down' ? '▼' : ''} {delta.value}
            </span>
          )}
          {hint && <span className="text-muted-foreground">{hint}</span>}
        </div>
      )}
    </Card>
  )
}

export default Stat
