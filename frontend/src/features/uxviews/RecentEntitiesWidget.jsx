// NTUX11 — Historique de navigation récente unifié : widget autonome
// (Dashboard) affichant `readRecentEntities()` (providers/commandActions.js —
// déjà alimenté par la palette ⌘K ET, depuis NTUX11, par tout `<DataTable
// trackRecent>` opt-in). Réutilise ROUTE/TYPE_LABEL/TYPE_ACCENT
// (lib/search/entityRoutes.js) — même table que la palette, aucune route
// dupliquée. Rend RIEN si la liste est vide (autonome, même patron que
// MesEquipesCard/ApprobationsAttentionCard sur ce Dashboard).
import { Clock } from 'lucide-react'
import { useNavigate } from 'react-router-dom'
import { Card, CardHeader, CardTitle, CardDescription, CardContent } from '../../ui'
import { readRecentEntities } from '../../providers/commandActions'
import { ROUTE, TYPE_LABEL, TYPE_ACCENT } from '../../lib/search/entityRoutes'
import { timeAgo } from '../../lib/format'

export default function RecentEntitiesWidget() {
  const navigate = useNavigate()
  const recent = readRecentEntities()
  if (!recent.length) return null

  return (
    <Card className="cv-auto" data-testid="recent-entities-widget">
      <CardHeader>
        <CardTitle className="flex items-center gap-2">
          <Clock className="size-4 text-muted-foreground" aria-hidden="true" />
          Récents
        </CardTitle>
        <CardDescription>Dernières fiches ouvertes — palette ⌘K et listes</CardDescription>
      </CardHeader>
      <CardContent>
        <ul className="flex flex-col gap-1">
          {recent.map((e) => {
            const make = ROUTE[e.type]
            return (
              <li key={`${e.type}-${e.id}`}>
                <button
                  type="button"
                  onClick={() => make && navigate(make(e.id))}
                  className="flex w-full items-center gap-2 rounded-lg px-2 py-1.5 text-left text-sm hover:bg-accent/60 focus-ring"
                >
                  {TYPE_ACCENT[e.type] && (
                    <span
                      className="size-1.5 shrink-0 rounded-full"
                      style={{ background: `var(--module-accent-${TYPE_ACCENT[e.type]})` }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="min-w-0 flex-1 truncate font-medium text-foreground">
                    {e.label || TYPE_LABEL[e.type] || e.type}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">{timeAgo(e.ts)}</span>
                </button>
              </li>
            )
          })}
        </ul>
      </CardContent>
    </Card>
  )
}
