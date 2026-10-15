import { Spinner } from './Spinner'

/* Bandeau « Tirer pour actualiser » / « Actualisation… » en tête d'un écran
   terrain (voir ui/usePullToRefresh : `pullDistance`, `refreshing`). Rien n'est
   rendu hors geste. Un seul endroit pour Interventions et Ma journée. */
export default function IndicateurTirerPourActualiser({ pullDistance, refreshing }) {
  if (!(pullDistance > 0 || refreshing)) return null
  return (
    <div
      className="flex items-center justify-center gap-2 text-xs text-muted-foreground"
      style={{ height: `${Math.max(pullDistance, refreshing ? 32 : 0)}px`, overflow: 'hidden', transition: refreshing ? 'height 150ms ease' : 'none' }}
      role="status"
    >
      {refreshing ? <Spinner className="size-4" /> : null}
      {refreshing ? 'Actualisation…' : 'Tirer pour actualiser'}
    </div>
  )
}
