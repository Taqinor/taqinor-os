// J143 — Squelette de chargement des chantiers, calqué sur la FORME du contenu
// (colonnes kanban, lignes de liste, grille calendrier) pour éviter tout saut de
// mise en page quand les vrais chantiers arrivent. Réutilise les primitives de
// squelette du système de design et les classes de mise en page existantes
// (kb-*, cal-*) afin que le squelette occupe exactement la place du contenu.
// Entièrement masqué aux lecteurs d'écran : le libellé « Chargement » reste dans
// la page (région live).
import { Skeleton } from '../../../ui'

const KANBAN_COLS = 5 // miroir de l'entonnoir chantier (statuses.js)
const CARDS_PER_COL = [3, 2, 2, 1, 1]
const LIST_ROWS = 8
const LIST_COLS = 5
const CAL_CELLS = 35 // 5 semaines × 7 jours

function CardSkeleton() {
  return (
    <div className="kb-card kc-card">
      <div className="kc-card-top">
        <Skeleton className="h-3.5 w-20" />
        <Skeleton className="h-5 w-16 rounded-full" />
      </div>
      <Skeleton className="mt-1 h-3 w-3/4" />
      <div className="kc-chips mt-2">
        <Skeleton className="h-4 w-16 rounded-full" />
        <Skeleton className="h-4 w-12 rounded-full" />
      </div>
      <Skeleton className="mt-2 h-2 w-full rounded-full" />
    </div>
  )
}

function KanbanSkeleton() {
  return (
    <div className="kb-board">
      {Array.from({ length: KANBAN_COLS }).map((unused, c) => (
        <section key={c} className="kb-col">
          <header className="kb-col-header">
            <div className="kb-col-title-row">
              <Skeleton className="h-3.5 w-24" />
              <Skeleton className="h-4 w-6 rounded-full" />
            </div>
          </header>
          <div className="kb-col-body">
            {Array.from({ length: CARDS_PER_COL[c] ?? 1 }).map((u, i) => (
              <CardSkeleton key={i} />
            ))}
          </div>
        </section>
      ))}
    </div>
  )
}

function ListSkeleton() {
  return (
    <div className="rounded-xl border border-border bg-card p-2">
      <table className="w-full">
        <tbody>
          {Array.from({ length: LIST_ROWS }).map((unused, r) => (
            <tr key={r}>
              {Array.from({ length: LIST_COLS }).map((u, c) => (
                <td key={c} className="px-3 py-2.5">
                  <Skeleton className={c === 0 ? 'h-3.5 w-3/4' : 'h-3.5 w-1/2'} />
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function CalendarSkeleton() {
  return (
    <div className="cal-root">
      <div className="cal-grid">
        {Array.from({ length: CAL_CELLS }).map((unused, i) => (
          <div key={i} className="cal-cell">
            <Skeleton className="h-3 w-5" />
            <div className="cal-chips mt-1 flex flex-col gap-1">
              {i % 3 === 0 && <Skeleton className="h-4 w-full rounded" />}
              {i % 4 === 0 && <Skeleton className="h-4 w-2/3 rounded" />}
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}

/**
 * @param {{ view?: 'liste'|'kanban'|'calendrier' }} props
 */
export default function InstallationsSkeleton({ view = 'liste' }) {
  return (
    <div aria-hidden="true">
      {view === 'kanban'
        ? <KanbanSkeleton />
        : view === 'calendrier'
          ? <CalendarSkeleton />
          : <ListSkeleton />}
    </div>
  )
}
