import { useEffect, useMemo, useState } from 'react'
import { LayoutGrid, Plus, Trash2 } from 'lucide-react'
import api from '../../api/axios'
import coreApi from '../../api/coreApi'
import reportingApi from '../../api/reportingApi'
import {
  Badge, Button, Card, CardContent, Checkbox, DataTable, EmptyState, IconButton,
  Label, Segmented, Select, SelectTrigger, SelectValue, SelectContent, SelectItem,
  Spinner,
} from '../../ui'
import { ResponsiveDialog } from '../../ui/ResponsiveDialog'
import { useConfirmDialog, toast } from '../../ui/confirm'
import { isDirty } from '../../ui/form-utils'
import { useNavigationGuard } from '../../hooks/useNavigationGuard'
import DashboardFilterBar from '../../features/reporting/DashboardFilterBar'

/* WR8 — Gestionnaire de configuration de tableau de bord (FG96).
   CRUD des configs par UTILISATEUR ou par PALIER de rôle : choix des cartes
   affichées. Réservé responsable/admin (gate route). company forcée serveur.

   XPLT9 — monte aussi `DashboardFilterBar` (jusque-là construit mais jamais
   monté nulle part) : un sélecteur de dashboard FG381 (`core.Dashboard`)
   au-dessus de sa barre de filtres globaux (plage de dates, commercial,
   canal, catégorie produit), persistés dans `layout.globalFilters`. */

// Libellés FR des clés de cartes (miroir de ALL_DASHBOARD_CARDS côté backend).
const CARD_LABELS = {
  kpis: 'Indicateurs clés',
  ca_mensuel: 'CA mensuel',
  top_produits: 'Top produits',
  statuts_factures: 'Statuts factures',
  conversion: 'Conversion',
  stock_alerte: 'Alertes stock',
  creances: 'Créances',
  pipeline: 'Pipeline',
  commercial: 'Commercial',
  // WIR22 — badge du contrôle d'intégrité inter-documents (YSERV13).
  integrite: "Contrôle d'intégrité",
  // WIR100 — KPI fédérés (ARC40) : tuiles agrégées des modules actifs.
  kpi_federes: 'KPI fédérés',
}
const ALL_CARDS = Object.keys(CARD_LABELS)

const TIERS = [
  { value: 'admin', label: 'Administrateur' },
  { value: 'responsable', label: 'Responsable' },
  { value: 'normal', label: 'Normal' },
]
const TIER_LABEL = Object.fromEntries(TIERS.map((t) => [t.value, t.label]))

const SCOPES = [
  { value: 'tier', label: 'Palier de rôle' },
  { value: 'user', label: 'Utilisateur' },
]

export default function DashboardConfigPage() {
  const { confirmDelete } = useConfirmDialog()
  const [configs, setConfigs] = useState([])
  const [users, setUsers] = useState([])
  const [effective, setEffective] = useState(null)
  const [loading, setLoading] = useState(true)

  const [dialogOpen, setDialogOpen] = useState(false)
  const [scope, setScope] = useState('tier')
  const [tier, setTier] = useState('normal')
  const [userId, setUserId] = useState('')
  const [cards, setCards] = useState([...ALL_CARDS])
  const [saving, setSaving] = useState(false)

  // VX169 — garde de navigation IN-APP : le dialogue de création réinitialise
  // toujours les mêmes valeurs par défaut (`openCreate`) — comparer à celles-ci
  // suffit à détecter une saisie perdue si l'utilisateur navigue en interne.
  const dirty = dialogOpen && isDirty(
    { scope: 'tier', tier: 'normal', userId: '', cards: ALL_CARDS },
    { scope, tier, userId, cards },
  )
  useNavigationGuard(dirty)

  // XPLT9 — dashboards FG381 (`core.Dashboard`) disponibles pour le filtre
  // global, et le dashboard actuellement sélectionné. `selectedLayout` est un
  // ÉTAT LOCAL (pas un simple dérivé) car `DashboardFilterBar` le met à jour
  // en écriture optimiste (`onLayoutChange`) avant confirmation serveur —
  // resynchronisé depuis `dashboards` UNIQUEMENT quand la sélection change
  // (pas à chaque refetch de la liste, pour ne jamais écraser une frappe en
  // cours dans la barre de filtres).
  const [dashboards, setDashboards] = useState([])
  const [selectedDashboardId, setSelectedDashboardId] = useState('')
  const [selectedLayout, setSelectedLayout] = useState(null)

  useEffect(() => {
    let active = true
    coreApi.dashboards.list()
      .then((r) => { if (active) setDashboards(r.data?.results ?? r.data ?? []) })
      .catch(() => { if (active) setDashboards([]) })
    return () => { active = false }
  }, [])

  const selectDashboard = (id) => {
    setSelectedDashboardId(id)
    const found = dashboards.find((d) => String(d.id) === String(id))
    setSelectedLayout(found?.layout ?? {})
  }

  const userName = useMemo(() => {
    const map = new Map(users.map((u) => [u.id, u]))
    return (id) => map.get(id)?.username || `Utilisateur #${id}`
  }, [users])

  const reload = () => reportingApi.listDashboardConfigs()
    .then((r) => setConfigs(r.data.results ?? r.data ?? []))
    .catch(() => setConfigs([]))

  useEffect(() => {
    let active = true
    Promise.all([
      reportingApi.listDashboardConfigs(),
      reportingApi.effectiveDashboardConfig(),
      api.get('/users/'),
    ])
      .then(([c, e, u]) => {
        if (!active) return
        setConfigs(c.data.results ?? c.data ?? [])
        setEffective(e.data)
        setUsers(u.data.results ?? u.data ?? [])
      })
      .catch(() => {})
      .finally(() => { if (active) setLoading(false) })
    return () => { active = false }
  }, [])

  const openCreate = () => {
    setScope('tier')
    setTier('normal')
    setUserId('')
    setCards([...ALL_CARDS])
    setDialogOpen(true)
  }

  const toggleCard = (key) =>
    setCards((cur) => cur.includes(key) ? cur.filter((k) => k !== key) : [...cur, key])

  const submit = (e) => {
    e.preventDefault()
    setSaving(true)
    // Config soit per-user (user, menu_tier vide) soit de palier (user null,
    // menu_tier) — jamais les deux (validé côté serveur).
    const payload = scope === 'user'
      ? { user: userId, cards }
      : { menu_tier: tier, cards }
    reportingApi.saveDashboardConfig(null, payload)
      .then(() => {
        toast.success('Configuration enregistrée.')
        setDialogOpen(false)
        reload()
      })
      .catch(() => toast.error('Échec de l’enregistrement de la configuration.'))
      .finally(() => setSaving(false))
  }

  const remove = async (cfg) => {
    const label = cfg.user ? userName(cfg.user) : (TIER_LABEL[cfg.menu_tier] || cfg.menu_tier)
    const ok = await confirmDelete({
      title: 'Supprimer cette configuration ?',
      description: `La configuration « ${label} » sera supprimée.`,
    })
    if (!ok) return
    reportingApi.deleteDashboardConfig(cfg.id)
      .then(() => { toast.success('Configuration supprimée.'); reload() })
      .catch(() => toast.error('Suppression impossible.'))
  }

  const columns = useMemo(() => [
    {
      id: 'scope', header: 'Portée', width: 160,
      accessor: (r) => (r.user ? 'Utilisateur' : 'Palier'),
      cell: (v, r) => (
        <Badge tone={r.user ? 'info' : 'primary'}>
          {r.user ? 'Utilisateur' : 'Palier de rôle'}
        </Badge>
      ),
    },
    {
      id: 'cible', header: 'Cible',
      accessor: (r) => (r.user ? userName(r.user) : (TIER_LABEL[r.menu_tier] || r.menu_tier)),
    },
    {
      id: 'cards', header: 'Cartes activées',
      accessor: (r) => (r.cards || []).length,
      cell: (v, r) => (
        <span className="text-sm text-muted-foreground">
          {(r.cards || []).map((k) => CARD_LABELS[k] || k).join(', ') || 'Aucune'}
        </span>
      ),
    },
    {
      id: 'actions', header: '', width: 70, align: 'right',
      accessor: () => '',
      cell: (v, r) => (
        <IconButton variant="ghost" label="Supprimer" onClick={() => remove(r)}>
          <Trash2 />
        </IconButton>
      ),
    },
  // eslint-disable-next-line react-hooks/exhaustive-deps -- remove recréé par rendu
  ], [userName])

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Configuration des tableaux de bord</h1>
        <div className="page-subtitle">
          Choisissez les cartes affichées par utilisateur ou par palier de rôle.
        </div>
      </div>

      {effective && (
        <Card className="mb-4">
          <CardContent className="flex flex-wrap items-center gap-2 p-4" data-testid="effective-config">
            <span className="text-sm font-semibold">Ma configuration effective</span>
            <Badge tone="neutral">{effective.source}</Badge>
            <span className="text-sm text-muted-foreground">
              {(effective.cards || []).map((k) => CARD_LABELS[k] || k).join(', ')}
            </span>
          </CardContent>
        </Card>
      )}

      {/* XPLT9 — sélecteur de dashboard FG381 + sa barre de filtres globaux
          (plage de dates, commercial, canal, catégorie produit), persistés
          dans `layout.globalFilters`. */}
      {dashboards.length > 0 && (
        <Card className="mb-4">
          <CardContent className="flex flex-col gap-3 p-4">
            <div className="flex flex-wrap items-center gap-3">
              <span className="text-sm font-semibold">Filtres globaux d’un tableau de bord</span>
              <Select value={selectedDashboardId} onValueChange={selectDashboard}>
                <SelectTrigger className="w-64" aria-label="Choisir un tableau de bord">
                  <SelectValue placeholder="Choisir un tableau de bord…" />
                </SelectTrigger>
                <SelectContent>
                  {dashboards.map((d) => (
                    <SelectItem key={d.id} value={String(d.id)}>{d.titre}</SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            {selectedDashboardId && (
              <DashboardFilterBar
                dashboardId={Number(selectedDashboardId)}
                layout={selectedLayout}
                onLayoutChange={setSelectedLayout}
                onReload={() => {}}
              />
            )}
          </CardContent>
        </Card>
      )}

      <div className="mb-4 flex justify-end">
        <Button onClick={openCreate}><Plus /> Nouvelle configuration</Button>
      </div>

      {loading ? (
        <p className="flex items-center gap-2 py-10 text-sm text-muted-foreground"><Spinner /> Chargement…</p>
      ) : configs.length === 0 ? (
        <EmptyState
          icon={LayoutGrid}
          title="Aucune configuration"
          description="Sans configuration, chaque utilisateur voit les cartes par défaut de son rôle."
          className="my-6"
        />
      ) : (
        <DataTable
          data={configs}
          columns={columns}
          getRowId={(row) => row.id}
          searchable={false}
          pageSize={25}
          aria-label="Configurations de tableau de bord"
        />
      )}

      {/* Dialogue de création */}
      <ResponsiveDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        title="Nouvelle configuration de tableau de bord"
        description="Une config est soit par palier de rôle, soit par utilisateur (jamais les deux)."
      >
        <form onSubmit={submit} noValidate className="flex flex-col gap-3">
          <div>
            <Label>Portée</Label>
            <div className="mt-1">
              <Segmented options={SCOPES} value={scope} onChange={setScope} aria-label="Portée de la configuration" />
            </div>
          </div>

          {scope === 'tier' ? (
            <div>
              <Label htmlFor="dc-tier">Palier de rôle</Label>
              <Select value={tier} onValueChange={setTier} aria-label="Palier de rôle">
                <SelectTrigger id="dc-tier"><SelectValue /></SelectTrigger>
                <SelectContent>
                  {TIERS.map((t) => <SelectItem key={t.value} value={t.value}>{t.label}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          ) : (
            <div>
              <Label htmlFor="dc-user">Utilisateur</Label>
              <Select value={userId} onValueChange={setUserId} aria-label="Utilisateur">
                <SelectTrigger id="dc-user"><SelectValue placeholder="Choisir un utilisateur…" /></SelectTrigger>
                <SelectContent>
                  {users.map((u) => <SelectItem key={u.id} value={String(u.id)}>{u.username}</SelectItem>)}
                </SelectContent>
              </Select>
            </div>
          )}

          <div>
            <Label>Cartes affichées</Label>
            <div className="mt-1 grid grid-cols-2 gap-2">
              {ALL_CARDS.map((key) => (
                <label key={key} className="flex items-center gap-2 text-sm">
                  <Checkbox checked={cards.includes(key)} onCheckedChange={() => toggleCard(key)} />
                  {CARD_LABELS[key]}
                </label>
              ))}
            </div>
          </div>

          <div className="flex justify-end gap-2">
            <Button type="button" variant="outline" onClick={() => setDialogOpen(false)}>Annuler</Button>
            <Button type="submit" loading={saving} disabled={scope === 'user' && !userId}>Créer</Button>
          </div>
        </form>
      </ResponsiveDialog>
    </div>
  )
}
