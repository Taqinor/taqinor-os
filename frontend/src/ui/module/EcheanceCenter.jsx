import { Link } from 'react-router-dom'
import { CalendarClock, AlertTriangle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Card } from '../Card'
import { Badge } from '../Badge'
import { Skeleton } from '../Skeleton'
import { EmptyState } from '../EmptyState'
import { daysUntil, urgencyLevel, urgencyTone, urgencyLabel, compareUrgency } from './urgency.js'

/* ============================================================================
   UX1 — Centre d'échéances.
   ----------------------------------------------------------------------------
   Liste compacte des prochaines échéances (contrats à renouveler, garanties SAV,
   contrôles QHSE, entretiens flotte…), triées « les plus urgentes / en retard en
   premier » (compareUrgency). Chaque ligne : un liseré coloré par ton d'urgence,
   le libellé (lien optionnel), une méta atténuée, et une pastille « J-N /
   En retard ». États chargement / erreur / vide gérés ici.

   items : [{ id, label, date?, daysLeft?, meta?, to?, tone? }]
   ========================================================================== */

// Liseré gauche coloré par ton (couleur jamais seul signal — la pastille répète).
const BORDER = {
  neutral: 'border-l-muted-foreground/40',
  info: 'border-l-info',
  success: 'border-l-success',
  warning: 'border-l-warning',
  danger: 'border-l-destructive',
}

export function EcheanceCenter({
  title = 'Échéances',
  items = [],
  loading,
  error,
  emptyText = 'Aucune échéance à venir.',
  className,
  max,
}) {
  // Calcule les jours restants manquants depuis `date`, puis trie par urgence.
  const rows = items
    .map((it) => ({
      ...it,
      daysLeft: it.daysLeft != null ? it.daysLeft : daysUntil(it.date),
    }))
    .sort(compareUrgency)

  const visible = typeof max === 'number' ? rows.slice(0, max) : rows

  return (
    <Card className={cn('p-4 sm:p-5', className)}>
      <div className="mb-3 flex items-center gap-2">
        <CalendarClock className="size-4 text-muted-foreground" aria-hidden="true" />
        <h3 className="font-display text-base font-semibold leading-tight tracking-tight">{title}</h3>
      </div>

      {loading ? (
        <ul className="flex flex-col gap-2">
          {Array.from({ length: 4 }).map((unused, i) => (
            <li key={i} className="flex items-center justify-between gap-3 rounded-lg border border-l-4 border-border px-3 py-2">
              <Skeleton className="h-4 w-1/2" />
              <Skeleton className="h-4 w-14" />
            </li>
          ))}
        </ul>
      ) : error ? (
        <EmptyState
          icon={AlertTriangle}
          title="Impossible de charger les échéances"
          description={typeof error === 'string' ? error : 'Une erreur est survenue.'}
          className="border-destructive/40"
        />
      ) : visible.length === 0 ? (
        <EmptyState icon={CalendarClock} title="Rien à échéance" description={emptyText} />
      ) : (
        <ul className="flex flex-col gap-2">
          {visible.map((it) => {
            const level = urgencyLevel(it.daysLeft)
            const tone = it.tone ?? urgencyTone(level)
            return (
              <li
                key={it.id}
                className={cn(
                  'flex items-center justify-between gap-3 rounded-lg border border-l-4 border-border bg-card px-3 py-2 text-sm',
                  BORDER[tone] ?? BORDER.neutral,
                )}
              >
                <div className="min-w-0">
                  {it.to ? (
                    <Link
                      to={it.to}
                      className="truncate font-medium text-foreground hover:underline focus-ring"
                    >
                      {it.label}
                    </Link>
                  ) : (
                    <span className="truncate font-medium text-foreground">{it.label}</span>
                  )}
                  {it.meta && <p className="truncate text-xs text-muted-foreground">{it.meta}</p>}
                </div>
                <Badge tone={tone} className="shrink-0 tabular-nums">
                  {urgencyLabel(it.daysLeft)}
                </Badge>
              </li>
            )
          })}
        </ul>
      )}
    </Card>
  )
}

export default EcheanceCenter
