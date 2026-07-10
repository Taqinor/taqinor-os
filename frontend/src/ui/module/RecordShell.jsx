import { Link } from 'react-router-dom'
import { ArrowLeft } from 'lucide-react'
import { cn } from '../../lib/cn'
import { StatusPill } from '../StatusPill'
import { Tabs, TabsList, TabsTrigger, TabsContent } from '../Tabs'
import { Button } from '../Button'
import { useOptimisticSave } from '../../hooks/useOptimisticSave'

/* ============================================================================
   ARC46 — Coquille d'enregistrement (le pendant détail/formulaire de ListShell).
   ----------------------------------------------------------------------------
   Là où `ListShell` (UX1) coiffe les LISTES, `RecordShell` coiffe une FICHE
   d'enregistrement : en-tête (retour + titre + statut + actions), corps en
   onglets (ou `children`), panneau latéral `chatter`/`activity` (historique),
   et — nouveauté vs `DetailShell` — une BARRE D'ENREGISTREMENT optionnelle
   branchée sur `useOptimisticSave` (édition optimiste + rollback). Le style est
   volontairement CALQUÉ sur `DetailShell` : AUCUNE refonte visuelle (VX possède
   le style), on ne fait qu'ajouter la save-bar et le nommage « record ».
   Futur consommateur nommé : VX23.

   ── Barre d'enregistrement (opt-in) ──
   Fournir `record` (l'enregistrement en cours d'édition) ET `onSave(record)`
   (l'appel réseau réel, qui REJETTE en cas d'échec) active la barre. Sans ces
   props, AUCUNE barre n'est rendue — la coquille se comporte alors exactement
   comme une fiche en lecture (comme `DetailShell`). `dirty` (par défaut : la
   présence d'un `record` différent de la valeur serveur suivie) pilote l'état
   actif du bouton ; le libellé d'état FR ('Enregistrement…' / 'Enregistré')
   vient de `useOptimisticSave`.

   tabs : [{ value, label, content, count? }]
   ========================================================================== */

export function RecordShell({
  title,
  subtitle,
  status,
  statusPill: StatusEl,
  actions,
  backTo,
  backLabel = 'Retour',
  tabs = [],
  activity,
  chatter,          // alias de `activity` (slot chatter) — futur consommateur VX23
  defaultTab,
  className,
  children,
  // ── Save-bar (opt-in) ──
  record,           // valeur serveur suivie (active la barre avec `onSave`)
  onSave,           // (record) => Promise — REJETTE en cas d'échec (rollback auto)
  dirty,            // bool optionnel : force l'état « modifié » de la barre
  saveLabel = 'Enregistrer',
  onSaveError,
}) {
  const aside = chatter ?? activity
  const hasSaveBar = typeof onSave === 'function'

  // Édition optimiste + rollback. `useOptimisticSave` suit `record` au repos.
  const { statusLabel, isSaving, save } = useOptimisticSave(record, {
    onError: onSaveError,
  })

  // « Modifié » : par défaut vrai si un record est fourni ; sinon piloté par
  // `dirty`. Le bouton reste bloqué pendant un enregistrement en cours.
  const isDirty = dirty ?? record != null

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
      {/* -------- En-tête (calqué sur DetailShell) -------- */}
      <div className="flex flex-col gap-2">
        {backTo && (
          <Link
            to={backTo}
            className="inline-flex w-fit items-center gap-1.5 text-sm text-muted-foreground transition-colors hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
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

      {/* -------- Corps (+ panneau chatter/activité optionnel) -------- */}
      {aside ? (
        <div className="lg:grid lg:grid-cols-[1fr_320px] lg:gap-6">
          <div className="min-w-0">{body}</div>
          <aside className="mt-4 lg:mt-0">{aside}</aside>
        </div>
      ) : (
        body
      )}

      {/* -------- Barre d'enregistrement (opt-in, branchée useOptimisticSave) -------- */}
      {hasSaveBar && (
        <div
          className="flex flex-wrap items-center justify-end gap-3 rounded-lg border border-border bg-card px-4 py-3"
          data-record-savebar
        >
          {statusLabel && (
            <span
              className="text-sm text-muted-foreground"
              aria-live="polite"
              data-record-savebar-status
            >
              {statusLabel}
            </span>
          )}
          <Button
            type="button"
            disabled={isSaving || !isDirty}
            aria-busy={isSaving}
            onClick={() => save(record, onSave)}
          >
            {isSaving ? 'Enregistrement…' : saveLabel}
          </Button>
        </div>
      )}
    </div>
  )
}

export default RecordShell
