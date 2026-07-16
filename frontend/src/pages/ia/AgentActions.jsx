import { useEffect, useMemo, useState } from 'react'
import { useHasPermission, useIsAdmin } from '../../hooks/useHasPermission'
import { Zap, ShieldAlert, ArrowRightLeft, Lock, History, Undo2 } from 'lucide-react'
import iaApi from '../../api/iaApi'
import {
  Badge, Card, CardContent, EmptyState, Input, Spinner,
  Tabs, TabsList, TabsTrigger, TabsContent, Button,
} from '../../ui'
import { formatDateTime } from '../../lib/format'

/* WR8 — Catalogue des actions agentiques (AG1). Liste, dans l'assistant, les
   actions pilotées par le registre que l'utilisateur courant a le droit
   d'exécuter, depuis GET /api/django/agent/actions/ (filtré par permission
   côté serveur). Métadonnées seules : cet écran N'EXÉCUTE rien — l'exécution
   reste la voie propose→confirme de l'agent (AG2/AG3).

   YHARD2 — un second onglet « Historique / annuler », réservé admin/Directeur,
   liste les actions IA CONFIRMÉES (GET /api/django/agent/logs/) et permet
   d'annuler celles qui sont réversibles (POST …/logs/<id>/annuler/). */

// Libellé + teinte FR du niveau de risque d'une action.
const RISK = {
  internal: { label: 'Interne', tone: 'neutral', icon: Zap },
  outward: { label: 'Sortant', tone: 'warning', icon: ArrowRightLeft },
  irreversible: { label: 'Irréversible', tone: 'danger', icon: ShieldAlert },
}

function ActionsCatalogue() {
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
    <>
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
    </>
  )
}

// VX153 — libellé de jour relatif pour regrouper le journal (Aujourd'hui / Hier
// / date longue). `confirmed_at` est déjà servi par l'API ; une entrée sans date
// tombe dans « Date inconnue » plutôt que de disparaître.
function dayLabel(iso) {
  if (!iso) return 'Date inconnue'
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return 'Date inconnue'
  const startOf = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate())
  const diffDays = Math.round((startOf(new Date()) - startOf(d)) / 86400000)
  if (diffDays === 0) return "Aujourd'hui"
  if (diffDays === 1) return 'Hier'
  return d.toLocaleDateString('fr-FR', { day: 'numeric', month: 'long', year: 'numeric' })
}

// VX153 — regroupe les logs par jour EN PRÉSERVANT l'ordre d'arrivée (l'ordre de
// l'API est conservé au sein d'un jour et entre les jours par première
// apparition), pour ne casser aucun consommateur qui indexe les lignes.
function groupLogsByDay(logs) {
  const order = []
  const map = new Map()
  for (const log of logs) {
    const label = dayLabel(log.confirmed_at)
    if (!map.has(label)) { map.set(label, []); order.push(label) }
    map.get(label).push(log)
  }
  return order.map((label) => ({ label, items: map.get(label) }))
}

// YHARD2 — journal des actions IA confirmées + annulation (admin/Directeur).
function ActionsHistorique() {
  const [logs, setLogs] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(false)
  const [undoingId, setUndoingId] = useState(null)
  const [undoError, setUndoError] = useState(null)
  // Bump pour redéclencher le chargement (après une annulation) sans appeler
  // setState de façon synchrone hors effet.
  const [reloadKey, setReloadKey] = useState(0)

  useEffect(() => {
    let active = true
    const load = async () => {
      setLoading(true)
      try {
        const r = await iaApi.getAgentActionLogs()
        if (active) { setLogs(r.data?.results ?? []); setError(false) }
      } catch {
        if (active) setError(true)
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [reloadKey])

  const undo = async (log) => {
    setUndoingId(log.id); setUndoError(null)
    try {
      await iaApi.undoAgentAction(log.id)
      setReloadKey((k) => k + 1)
    } catch (e) {
      setUndoError(e?.response?.data?.detail ?? 'Annulation impossible.')
    } finally {
      setUndoingId(null)
    }
  }

  if (loading) return (
    <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
  )
  if (error) {
    return (
      <EmptyState
        icon={Lock}
        title="Impossible de charger l’historique"
        description="Une erreur est survenue lors du chargement du journal des actions IA."
        className="my-6"
      />
    )
  }
  if (logs.length === 0) {
    return (
      <EmptyState
        icon={History}
        title="Aucune action confirmée"
        description="Les actions IA confirmées par un utilisateur apparaîtront ici."
        className="my-6"
      />
    )
  }

  return (
    <div className="flex flex-col gap-4">
      {undoError && <div className="form-error-box">{undoError}</div>}
      {/* VX153 — journal groupé par jour (Aujourd'hui / Hier / date). */}
      {groupLogsByDay(logs).map((group) => (
        <section key={group.label} className="flex flex-col gap-2">
          <h3 className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
            {group.label}
          </h3>
          {group.items.map((log) => {
            const risk = RISK[log.risk_level] || RISK.internal
            return (
              <Card key={log.id} data-testid="action-log-row">
                <CardContent className="flex flex-wrap items-center gap-2 p-3">
                  <div className="min-w-[180px] flex-1">
                    <div className="flex items-center gap-1.5">
                      <span className="font-medium text-sm">{log.object_repr || log.action_key}</span>
                      <Badge tone={risk.tone}>{risk.label}</Badge>
                      {log.undone_at && <Badge tone="neutral">Annulée</Badge>}
                    </div>
                    <div className="text-xs text-muted-foreground">
                      {log.user || '—'} · {log.confirmed_at ? formatDateTime(log.confirmed_at) : '—'}
                    </div>
                  </div>
                  <Button
                    type="button"
                    size="sm"
                    variant="outline"
                    disabled={!log.is_undoable || Boolean(log.undone_at) || undoingId === log.id}
                    onClick={() => undo(log)}
                  >
                    <Undo2 className="size-4" aria-hidden="true" />
                    {log.undone_at ? 'Déjà annulée' : undoingId === log.id ? 'Annulation…' : 'Annuler'}
                  </Button>
                </CardContent>
              </Card>
            )
          })}
        </section>
      ))}
    </div>
  )
}

export default function AgentActions() {
  // YHARD2 — le journal des actions IA est un réglage interne sensible,
  // réservé admin/Directeur (le backend re-vérifie : IsAdminRole). Les deux
  // hooks sont appelés inconditionnellement (règle des hooks) puis combinés.
  const isAdmin = useIsAdmin()
  const isDirecteur = useHasPermission(null, ['Directeur'])
  const canViewHistorique = isAdmin || isDirecteur

  return (
    <div className="page" data-testid="agent-actions">
      <div className="page-header">
        <h1 className="page-title">Actions de l’assistant</h1>
        <div className="page-subtitle">
          Actions que vous pouvez déclencher via l’assistant. Chacune se confirme avant exécution.
        </div>
      </div>

      {canViewHistorique ? (
        <Tabs defaultValue="catalogue">
          <TabsList className="mb-4">
            <TabsTrigger value="catalogue">Catalogue</TabsTrigger>
            <TabsTrigger value="historique">Historique / annuler</TabsTrigger>
          </TabsList>
          <TabsContent value="catalogue">
            <ActionsCatalogue />
          </TabsContent>
          <TabsContent value="historique">
            <ActionsHistorique />
          </TabsContent>
        </Tabs>
      ) : (
        <ActionsCatalogue />
      )}
    </div>
  )
}
