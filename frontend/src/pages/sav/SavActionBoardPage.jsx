// ZSAV6 — Tableau « Action requise » : tickets ouverts groupés par action
// attendue (à répondre / à planifier / à relancer / à clôturer / sans
// action), parité Odoo « Activity view ». Réservé responsable/admin.
import { useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import { AlertTriangle, MessageCircleQuestion, CalendarClock, Bell, CheckCircle2, Circle } from 'lucide-react'
import savApi from '../../api/savApi'
import { TooltipProvider, Card, Badge, EmptyState, Skeleton, Button } from '../../ui'

const BUCKETS = [
  { key: 'a_repondre', label: 'À répondre', icon: MessageCircleQuestion, tone: 'danger' },
  { key: 'a_planifier', label: 'À planifier', icon: CalendarClock, tone: 'warning' },
  { key: 'a_relancer', label: 'À relancer', icon: Bell, tone: 'warning' },
  { key: 'a_cloturer', label: 'À clôturer', icon: CheckCircle2, tone: 'info' },
  { key: 'sans_action', label: 'Sans action', icon: Circle, tone: 'neutral' },
]

export default function SavActionBoardPage() {
  const [board, setBoard] = useState(null)
  const [tickets, setTickets] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const load = () => savApi.getSavFileAction()
    .then((r) => {
      setBoard(r.data)
      const allIds = Object.values(r.data.buckets ?? {}).flatMap((b) => b.ids)
      if (allIds.length === 0) { setTickets({}); return }
      // Récupère les références/clients affichés — la liste des tickets
      // ouverts suffit largement (pas de pagination attendue sur ce volume).
      return savApi.getTickets({ ouvert: 'tous' }).then((tr) => {
        const rows = tr.data.results ?? tr.data ?? []
        const map = {}
        for (const t of rows) map[t.id] = t
        setTickets(map)
      })
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  const charger = () => { setLoading(true); setLoadError(false); return load() }

  useEffect(() => { load() }, [])

  const totalCount = useMemo(() => {
    if (!board) return 0
    return Object.values(board.buckets ?? {}).reduce((sum, b) => sum + b.count, 0)
  }, [board])

  if (loading) {
    return (
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-4 p-1">
        {Array.from({ length: 3 }).map((_, i) => <Skeleton key={i} className="h-40 w-full" />)}
      </div>
    )
  }
  if (loadError || !board) {
    return (
      <div className="ui-root mx-auto max-w-6xl p-1">
        <EmptyState icon={AlertTriangle} title="Chargement impossible"
                    description="Le tableau d'action n'a pas pu être chargé. Réessayez."
                    action={<Button size="sm" variant="outline" onClick={charger}>Réessayer</Button>} />
      </div>
    )
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <header>
          <h1 className="font-display text-2xl font-bold tracking-tight">Action requise</h1>
          <p className="text-sm text-muted-foreground">
            {totalCount} ticket{totalCount > 1 ? 's' : ''} ouvert{totalCount > 1 ? 's' : ''}
          </p>
        </header>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {BUCKETS.map(({ key, label, icon: Icon, tone }) => {
            const bucket = board.buckets?.[key] ?? { count: 0, ids: [] }
            return (
              <Card key={key} className="flex flex-col gap-2 p-3">
                <div className="flex items-center gap-2">
                  {Icon && <Icon className="size-4 text-muted-foreground" aria-hidden="true" />}
                  <span className="flex-1 font-display text-sm font-semibold">{label}</span>
                  <Badge tone={tone}>{bucket.count}</Badge>
                </div>
                {bucket.ids.length === 0 ? (
                  <p className="text-xs text-muted-foreground">Aucun ticket.</p>
                ) : (
                  <ul className="flex flex-col gap-1">
                    {bucket.ids.slice(0, 20).map((id) => {
                      const t = tickets[id]
                      return (
                        <li key={id}>
                          <Link to="/sav" className="text-xs text-primary hover:underline">
                            {t?.reference ?? `#${id}`}{t?.client_nom ? ` — ${t.client_nom}` : ''}
                          </Link>
                        </li>
                      )
                    })}
                    {bucket.ids.length > 20 && (
                      <li className="text-xs text-muted-foreground">
                        + {bucket.ids.length - 20} autre(s)
                      </li>
                    )}
                  </ul>
                )}
              </Card>
            )
          })}
        </div>
      </div>
    </TooltipProvider>
  )
}
