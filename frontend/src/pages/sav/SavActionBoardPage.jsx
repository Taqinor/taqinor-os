// ZSAV6 — Tableau « Action requise » : tickets ouverts groupés par action
// attendue (à répondre / à planifier / à relancer / à clôturer / sans
// action), parité Odoo « Activity view ». Réservé responsable/admin.
import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { MessageCircleQuestion, CalendarClock, Bell, CheckCircle2, Circle } from 'lucide-react'
import savApi from '../../api/savApi'
import { ROUTE } from '../../lib/search/entityRoutes'
import { fetchAllPages } from '../../utils/fetchAllPages'
import { TooltipProvider } from '../../ui'
import { EtatActionBoard, EnTeteActionBoard, CartePanier, useTotalBuckets } from '../../ui/module/ActionBoard'

// ASAV52 — liste lue EN ENTIER (toutes les pages DRF), jamais la page 1 prise
// pour le total.
const lireTout = (appel, params = {}) => fetchAllPages(
  (page) => appel({ ...params, page, page_size: 200 }).then((r) => r.data),
).then((res) => (Array.isArray(res) ? res : (res?.results ?? [])))

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
      // ouverts, lue EN ENTIER (ASAV52) : toute référence de seau est résolue.
      return lireTout(savApi.getTickets, { ouvert: 'tous' }).then((rows) => {
        const map = {}
        for (const t of rows) map[t.id] = t
        setTickets(map)
      })
    })
    .catch(() => setLoadError(true))
    .finally(() => setLoading(false))

  const charger = () => { setLoading(true); setLoadError(false); return load() }

  useEffect(() => { load() }, [])

  const totalCount = useTotalBuckets(board)

  if (loading || loadError || !board) {
    return <EtatActionBoard loading={loading} squelettes={3} onRetry={charger} />
  }

  return (
    <TooltipProvider delayDuration={200}>
      <div className="ui-root mx-auto flex max-w-6xl flex-col gap-5 p-1">
        <EnTeteActionBoard titre="Action requise" sousTitre={<>{totalCount} ticket{totalCount > 1 ? 's' : ''} ouvert{totalCount > 1 ? 's' : ''}</>} />

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 xl:grid-cols-5">
          {BUCKETS.map(({ key, label, icon: Icon, tone }) => {
            const bucket = board.buckets?.[key] ?? { count: 0, ids: [] }
            return (
              <CartePanier key={key} Icon={Icon} label={label} tone={tone} count={bucket.count}
                ids={bucket.ids} vide="Aucun ticket."
                renderId={(id) => {
                  const t = tickets[id]
                  return (
                    <li key={id}>
                      <Link to={ROUTE.ticket(id)} className="text-xs text-primary hover:underline">
                        {t?.reference ?? `#${id}`}{t?.client_nom ? ` — ${t.client_nom}` : ''}
                      </Link>
                    </li>
                  )
                }} />
            )
          })}
        </div>
      </div>
    </TooltipProvider>
  )
}
