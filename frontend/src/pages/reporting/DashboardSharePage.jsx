import { useEffect, useMemo, useState } from 'react'
import { Copy, Link2, Plus, Ban } from 'lucide-react'
import coreApi from '../../api/coreApi'
import {
  Badge, Button, DataTable, EmptyState, Select, SelectTrigger, SelectValue,
  SelectContent, SelectItem, Spinner,
} from '../../ui'
import { toast } from '../../ui/confirm'

/* ============================================================================
   XPLT10 — Partage de dashboard : lien public tokenisé (créer/révoquer).
   ----------------------------------------------------------------------------
   `core.PartageDashboard` — un lien PUBLIC lecture seule par dashboard, sans
   login (résolu depuis le seul jeton, `GET /core/dashboards-partages/public/
   <token>/`). Révoquer = kill-switch (`actif=False`), jamais de suppression
   physique tant que non explicitement demandée. Le mode TV (rotation plein
   écran) vit dans `DashboardsTvPage` (`/dashboards-tv`).
   ========================================================================== */

function publicUrl(token) {
  return `${window.location.origin}/dashboards-partages/public/${token}`
}

export default function DashboardSharePage() {
  const [dashboards, setDashboards] = useState([])
  const [partages, setPartages] = useState([])
  const [loading, setLoading] = useState(true)
  const [selectedDashboard, setSelectedDashboard] = useState('')
  const [creating, setCreating] = useState(false)

  const dashboardTitle = useMemo(() => {
    const map = new Map(dashboards.map((d) => [d.id, d]))
    return (id) => map.get(id)?.titre || `Dashboard #${id}`
  }, [dashboards])

  const reload = () => coreApi.dashboardsPartages.list()
    .then((r) => setPartages(r.data?.results ?? r.data ?? []))
    .catch(() => setPartages([]))

  useEffect(() => {
    let active = true
    Promise.all([coreApi.dashboards.list(), coreApi.dashboardsPartages.list()])
      .then(([d, p]) => {
        if (!active) return
        setDashboards(d.data?.results ?? d.data ?? [])
        setPartages(p.data?.results ?? p.data ?? [])
      })
      .catch(() => { if (active) { setDashboards([]); setPartages([]) } })
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const creerLien = () => {
    if (!selectedDashboard) return
    setCreating(true)
    coreApi.dashboardsPartages.create(selectedDashboard)
      .then(() => {
        toast.success('Lien de partage créé.')
        setSelectedDashboard('')
        reload()
      })
      .catch((err) => toast.error(err?.response?.data?.detail || 'Création du lien impossible.'))
      .finally(() => setCreating(false))
  }

  const revoquer = (partage) => {
    coreApi.dashboardsPartages.revoke(partage.id)
      .then(() => { toast.success('Lien révoqué.'); reload() })
      .catch(() => toast.error('Révocation impossible.'))
  }

  const copier = async (token) => {
    try {
      await navigator.clipboard.writeText(publicUrl(token))
      toast.success('Lien copié.')
    } catch {
      toast.error('Copie impossible — copiez le lien manuellement.')
    }
  }

  const columns = useMemo(() => [
    {
      id: 'dashboard', header: 'Dashboard',
      accessor: (r) => dashboardTitle(r.dashboard),
    },
    {
      id: 'lien', header: 'Lien public',
      accessor: (r) => publicUrl(r.token),
      cell: (v, r) => (
        <div className="flex items-center gap-2">
          <code className="truncate text-xs text-muted-foreground">{publicUrl(r.token)}</code>
          <Button size="sm" variant="ghost" onClick={() => copier(r.token)}>
            <Copy /> Copier
          </Button>
        </div>
      ),
    },
    {
      id: 'statut', header: 'Statut', width: 120,
      accessor: (r) => (r.actif ? 'Actif' : 'Révoqué'),
      cell: (v, r) => <Badge tone={r.actif ? 'success' : 'neutral'}>{r.actif ? 'Actif' : 'Révoqué'}</Badge>,
    },
    {
      id: 'actions', header: '', width: 120, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        r.actif ? (
          <Button size="sm" variant="ghost" onClick={() => revoquer(r)} data-testid={`revoke-partage-${r.id}`}>
            <Ban /> Révoquer
          </Button>
        ) : null
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- callbacks recréés par rendu
  ], [dashboardTitle])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Partage de tableaux de bord</h1>
        <div className="page-subtitle">
          Liens publics tokenisés, lecture seule, sans login — révocables à tout moment.
        </div>
      </div>

      <div className="mb-4 flex flex-wrap items-end gap-3">
        <div className="flex flex-col gap-1">
          <span className="text-xs font-medium text-muted-foreground">Dashboard</span>
          <Select value={selectedDashboard} onValueChange={setSelectedDashboard}>
            <SelectTrigger className="w-64" aria-label="Choisir un dashboard"><SelectValue placeholder="Choisir un dashboard…" /></SelectTrigger>
            <SelectContent>
              {dashboards.map((d) => <SelectItem key={d.id} value={String(d.id)}>{d.titre}</SelectItem>)}
            </SelectContent>
          </Select>
        </div>
        <Button onClick={creerLien} disabled={!selectedDashboard || creating} loading={creating}>
          <Plus /> Créer un lien de partage
        </Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : partages.length === 0 ? (
        <EmptyState
          icon={Link2}
          title="Aucun lien de partage"
          description="Créez un lien public pour partager un dashboard en lecture seule."
          className="my-6"
        />
      ) : (
        <DataTable
          data={partages}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Liens de partage de tableaux de bord"
        />
      )}
    </div>
  )
}
