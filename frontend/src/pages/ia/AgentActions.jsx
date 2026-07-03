import { useEffect, useMemo, useState } from 'react'
import { Zap, ShieldAlert, ArrowRightLeft, Lock } from 'lucide-react'
import iaApi from '../../api/iaApi'
import { Badge, Card, CardContent, EmptyState, Input, Spinner } from '../../ui'

/* WR8 — Catalogue des actions agentiques (AG1). Liste, dans l'assistant, les
   actions pilotées par le registre que l'utilisateur courant a le droit
   d'exécuter, depuis GET /api/django/agent/actions/ (filtré par permission
   côté serveur). Métadonnées seules : cet écran N'EXÉCUTE rien — l'exécution
   reste la voie propose→confirme de l'agent (AG2/AG3). */

// Libellé + teinte FR du niveau de risque d'une action.
const RISK = {
  internal: { label: 'Interne', tone: 'neutral', icon: Zap },
  outward: { label: 'Sortant', tone: 'warning', icon: ArrowRightLeft },
  irreversible: { label: 'Irréversible', tone: 'danger', icon: ShieldAlert },
}

export default function AgentActions() {
  const [actions, setActions] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [q, setQ] = useState('')

  useEffect(() => {
    let active = true
    iaApi.getAgentActions()
      .then((r) => { if (active) { setActions(r.data?.actions ?? []); setError(false) } })
      .catch(() => { if (active) setError(true) })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const filtered = useMemo(() => {
    const needle = q.trim().toLowerCase()
    if (!needle) return actions
    return actions.filter((a) =>
      (a.label || '').toLowerCase().includes(needle)
      || (a.description || '').toLowerCase().includes(needle)
      || (a.key || '').toLowerCase().includes(needle))
  }, [actions, q])

  return (
    <div className="page" data-testid="agent-actions">
      <div className="page-header">
        <h1 className="page-title">Actions de l’assistant</h1>
        <div className="page-subtitle">
          Actions que vous pouvez déclencher via l’assistant. Chacune se confirme avant exécution.
        </div>
      </div>

      <div className="mb-4 max-w-md">
        <Input
          type="search"
          placeholder="Rechercher une action…"
          value={q}
          onChange={(e) => setQ(e.target.value)}
          aria-label="Rechercher une action"
        />
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : error ? (
        <EmptyState
          icon={Lock}
          title="Impossible de charger les actions"
          description="Une erreur est survenue lors du chargement du catalogue d’actions."
          className="my-6"
        />
      ) : filtered.length === 0 ? (
        <EmptyState
          icon={Zap}
          title={actions.length === 0 ? 'Aucune action disponible' : 'Aucun résultat'}
          description={actions.length === 0
            ? 'Aucune action agentique n’est disponible pour votre rôle.'
            : 'Aucune action ne correspond à votre recherche.'}
          className="my-6"
        />
      ) : (
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {filtered.map((a) => {
            const risk = RISK[a.risk] || RISK.internal
            const RiskIcon = risk.icon
            return (
              <Card key={a.key} data-testid="action-card">
                <CardContent className="flex flex-col gap-2 p-4">
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-display text-sm font-semibold leading-tight">{a.label}</span>
                    <Badge tone={risk.tone}>
                      <RiskIcon className="size-3.5" aria-hidden="true" />
                      {risk.label}
                    </Badge>
                  </div>
                  {a.description && (
                    <p className="text-sm text-muted-foreground">{a.description}</p>
                  )}
                  <div className="mt-1 flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                    <span className="rounded bg-muted px-1.5 py-0.5 font-mono">{a.method}</span>
                    {a.required_permission && (
                      <span className="inline-flex items-center gap-1">
                        <Lock className="size-3" aria-hidden="true" />
                        {a.required_permission}
                      </span>
                    )}
                  </div>
                </CardContent>
              </Card>
            )
          })}
        </div>
      )}
    </div>
  )
}
