// QX29 — « Relances du jour » : le tableau d'action des devis, miroir de
// SavActionBoardPage (ZSAV6/parité Odoo « Activity view »). Répond à « quelles
// propositions ai-je besoin de traiter aujourd'hui ? » — Dashboard reste
// analytics-only, DevisList n'a qu'un bandeau d'expiration passif.
// Buckets : envoyés sans réponse (par palier de cadence), acceptés non
// facturés (réutilise le sélecteur ZFAC12 côté serveur), refusés sans motif
// (QX26), expirant bientôt. Chaque ligne se lie en profondeur via ?devis=<pk>
// (QX12) avec des raccourcis tel:/wa.me directs.
import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import {
  AlertTriangle, Clock, FileWarning, HelpCircle, PhoneCall, MessageCircle,
} from 'lucide-react'
import ventesApi from '../../api/ventesApi'
import { TooltipProvider, Card, Badge, EmptyState, Skeleton, Button } from '../../ui'
import { formatMAD } from '../../lib/format'

const BUCKETS = [
  { key: 'envoyes_sans_reponse', label: 'Envoyés sans réponse', icon: Clock, tone: 'warning' },
  { key: 'acceptes_non_factures', label: 'Acceptés non facturés', icon: AlertTriangle, tone: 'danger' },
  { key: 'refuses_sans_motif', label: 'Refusés sans motif', icon: HelpCircle, tone: 'neutral' },
  { key: 'expirant_bientot', label: 'Expirant bientôt', icon: FileWarning, tone: 'warning' },
]

// Numéro nettoyé pour un lien tel: / wa.me (chiffres et + initial), miroir de
// LeadCard.jsx (crm/leads/views/LeadCard.jsx) — pas d'import cross-app, la
// logique est triviale et dupliquée intentionnellement (deux lanes séparées).
const telHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const cleaned = s.replace(/[^\d+]/g, '')
  return cleaned ? `tel:${cleaned}` : null
}
const waHref = (raw) => {
  const s = String(raw ?? '').trim()
  if (!s) return null
  const digits = s.replace(/\D/g, '')
  return digits ? `https://wa.me/${digits}` : null
}

export default function DevisActionBoardPage() {
  const navigate = useNavigate()
  const [board, setBoard] = useState(null)
  const [devisMap, setDevisMap] = useState({})
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)

  const load = () => ventesApi.getDevisActionBoard()
    .then((r) => {
      setBoard(r.data)
      const allIds = Object.values(r.data.buckets ?? {}).flatMap((b) => b.ids)
      if (allIds.length === 0) { setDevisMap({}); return }
      // Le volume attendu (devis nécessitant une action) ne justifie pas de
      // pagination — même approche que ZSAV6 (getTickets({ ouvert: 'tous' })).
      return ventesApi.getDevis({}).then((dr) => {
        const rows = dr.data.results ?? dr.data ?? []
        const map = {}
        for (const d of rows) map[d.id] = d
        setDevisMap(map)
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
        {Array.from({ length: 4 }).map((unused, i) => <Skeleton key={i} className="h-40 w-full" />)}
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
          <h1 className="font-display text-2xl font-bold tracking-tight">Relances du jour</h1>
          <p className="text-sm text-muted-foreground">
            {totalCount} devis{totalCount > 1 ? '' : ''} nécessitant une action
          </p>
        </header>

        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-2 xl:grid-cols-4">
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
                  <p className="text-xs text-muted-foreground">Aucun devis.</p>
                ) : (
                  <ul className="flex flex-col gap-1.5">
                    {bucket.ids.slice(0, 20).map((id) => {
                      const d = devisMap[id]
                      const tel = telHref(d?.client_telephone ?? d?.telephone)
                      const wa = waHref(d?.client_whatsapp ?? d?.client_telephone ?? d?.telephone)
                      return (
                        <li key={id} className="flex items-center gap-1.5">
                          <button
                            type="button"
                            className="flex-1 truncate text-left text-xs text-primary hover:underline"
                            onClick={() => navigate(`/ventes/devis?devis=${id}`)}
                            title={d?.total_ttc != null ? formatMAD(d.total_ttc) : undefined}
                          >
                            {d?.reference ?? `#${id}`}{d?.client_nom ? ` — ${d.client_nom}` : ''}
                          </button>
                          {tel && (
                            <a href={tel} title="Appeler" aria-label={`Appeler ${d?.client_nom ?? ''}`}
                               className="text-muted-foreground hover:text-foreground">
                              <PhoneCall className="size-3.5" aria-hidden="true" />
                            </a>
                          )}
                          {wa && (
                            <a href={wa} target="_blank" rel="noopener noreferrer" title="Ouvrir WhatsApp"
                               aria-label={`WhatsApp ${d?.client_nom ?? ''}`}
                               className="text-muted-foreground hover:text-foreground">
                              <MessageCircle className="size-3.5" aria-hidden="true" />
                            </a>
                          )}
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
