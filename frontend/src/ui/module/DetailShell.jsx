import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '../../lib/cn'
import { StatusPill } from '../StatusPill'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../Tabs'

/* ============================================================================
   UX1 — Coquille de détail d'un enregistrement.
   ----------------------------------------------------------------------------
   En-tête (retour + titre + statut + actions), corps en onglets (ou `children`
   simple), et panneau latéral optionnel `activity` (chatter / historique) sur
   grand écran. Le statut est rendu via une Pill de module (`statusPill`) si
   fournie, sinon via le StatusPill générique.

   tabs : [{ value, label, content, count? }]
   `footer` (ARC46) : slot optionnel rendu SOUS le corps (ex. la barre
   d'enregistrement de RecordShell). Null par défaut — zéro changement de
   comportement pour les pages existantes.
   ========================================================================== */

export function DetailShell({
  title,
  subtitle,
  status,
  statusPill: StatusEl,
  actions,
  backTo,
  backLabel = 'Retour',
  tabs = [],
  activity,
  defaultTab,
  className,
  children,
  footer = null,
}) {
  const hasTabs = tabs.length > 0
  const body = hasTabs ? (
    <Tabs defaultValue={defaultTab ?? tabs[0]?.value}>
      <TabsList className="flex-wrap">
        {tabs.map((t) => (
          <TabsTrigger key={t.value} value={t.value}>
            {t.label}
            {typeof t.count === 'number' && (
              <span className="ml-1.5 rounded bg-muted px-1.5 text-xs tabular-nums text-muted-foreground">
                {t.count}
              </span>
            )}
          </TabsTrigger>
        ))}
      </TabsList>
      {tabs.map((t) => (
        <TabsContent key={t.value} value={t.value}>
          {t.content}
        </TabsContent>
      ))}
    </Tabs>
  ) : (
    children
  )

  return (
    <div className={cn('flex flex-col gap-4', className)}>
      {/* -------- En-tête -------- */}
      <div className="flex flex-col gap-2">
        {backTo && (
          <Link
            to={backTo}
            className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-ring"
          >
            <ArrowLeft className="size-4" aria-hidden="true" />
            {backLabel}
          </Link>
        )}
        <div className="flex flex-wrap items-start justify-between gap-3">
          <div className="min-w-0">
            <div className="flex flex-wrap items-center gap-2">
              <h1 className="font-display text-xl font-semibold tracking-tight">{title}</h1>
              {status != null &&
                (StatusEl ? <StatusEl status={status} /> : <StatusPill status={status} />)}
            </div>
            {subtitle && <p className="mt-0.5 text-sm text-muted-foreground">{subtitle}</p>}
          </div>
          {actions && <div className="flex flex-shrink-0 items-center gap-2">{actions}</div>}
        </div>
      </div>

      {/* -------- Corps (+ panneau d'activité optionnel) -------- */}
      {activity ? (
        <div className="lg:grid lg:grid-cols-[1fr_320px] lg:gap-6">
          <div className="min-w-0">{body}</div>
          <aside className="mt-4 lg:mt-0">{activity}</aside>
        </div>
      ) : (
        body
      )}

      {/* -------- Pied optionnel (ARC46 — ex. save-bar de RecordShell) -------- */}
      {footer}
    </div>
  )
}

export default DetailShell
