import { timeAgo } from '../../lib/format'

/* ENF19 — badge de fraîcheur VX30 partagé (extrait de Co2Page.jsx / FleetPage.jsx) :
   distinct visuellement d'un « 0 » réel (jamais la même couleur/forme qu'un
   état périmé). */
export default function FreshnessBadge({ stale, lastUpdated }) {
  return (
    <span
      className={
        stale
          ? 'inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning'
          : 'text-xs text-muted-foreground'
      }
    >
      {stale ? 'Hors-ligne — ' : 'Actualisé '}
      {timeAgo(lastUpdated)}
    </span>
  )
}
