import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Card } from '../Card'
import { Stat } from '../Stat'
import { Skeleton } from '../Skeleton'
import { EmptyState } from '../EmptyState'

/* ============================================================================
   UX1 — Tableau de bord de module.
   ----------------------------------------------------------------------------
   Bandeau de KPI (Stat) + zone de graphiques réutilisable par tous les modules
   ERP. Chaque KPI peut être cliquable (`to`) pour ouvrir la liste filtrée
   correspondante. États chargement (squelettes calqués sur le bandeau) et
   erreur (EmptyState en français) gérés une seule fois ici.

   stats  : [{ label, value, hint?, delta?, icon?, to?, tone? }]
   charts : [{ title, node, span? }]   (span === 'full' → pleine largeur)
   VX157 — `tone` (ex. "impact") passe telle quelle à <Stat> pour les
   grandeurs d'impact positif (production, CO₂ évité, économies…). */

export function ModuleDashboard({
  stats = [],
  charts = [],
  loading = false,
  error = null,
  className,
}) {
  if (error) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Impossible de charger le tableau de bord"
        description={typeof error === 'string' ? error : 'Une erreur est survenue lors du chargement des indicateurs.'}
        className={cn('border-destructive/40', className)}
      />
    )
  }

  return (
    <div className={cn('flex flex-col gap-6', className)}>
      {/* -------- Bandeau de KPI -------- */}
      {loading ? (
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 4 }).map((unused, i) => (
            <Card key={i} className="p-4 sm:p-5">
              <Skeleton className="h-3.5 w-1/2" />
              <Skeleton className="mt-3 h-7 w-2/3" />
              <Skeleton className="mt-2 h-3 w-1/3" />
            </Card>
          ))}
        </div>
      ) : (
        stats.length > 0 && (
          <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
            {stats.map((s, i) => {
              const stat = (
                <Stat
                  label={s.label}
                  value={s.value}
                  hint={s.hint}
                  delta={s.delta}
                  icon={s.icon}
                  tone={s.tone}
                />
              )
              return s.to ? (
                <Link
                  key={s.to + i}
                  to={s.to}
                  className="block rounded-xl transition-shadow hover:ring-2 hover:ring-ring/40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                >
                  {stat}
                </Link>
              ) : (
                <div key={i}>{stat}</div>
              )
            })}
          </div>
        )
      )}

      {/* -------- Graphiques -------- */}
      {!loading && charts.length > 0 && (
        <div className="grid gap-4 lg:grid-cols-2">
          {charts.map((c, i) => (
            <Card
              key={i}
              className={cn('p-4 sm:p-5', c.span === 'full' && 'lg:col-span-2')}
            >
              {c.title && (
                <h3 className="mb-3 font-display text-base font-semibold leading-tight tracking-tight">
                  {c.title}
                </h3>
              )}
              {c.node}
            </Card>
          ))}
        </div>
      )}
    </div>
  )
}

export default ModuleDashboard
