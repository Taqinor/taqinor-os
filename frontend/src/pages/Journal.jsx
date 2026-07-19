import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'
import { useHasPermission, useIsAdmin } from '../hooks/useHasPermission'
import { History, Download } from 'lucide-react'
import auditApi from '../api/auditApi'
import reportingApi from '../api/reportingApi'
import {
  Card, CardHeader, CardTitle, CardContent, Segmented, MultiSelect,
  Button, Badge, Skeleton, EmptyState, IconButton,
  Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter, DialogClose,
  Tabs, TabsList, TabsTrigger, TabsContent,
} from '../ui'
// VX28/VX148 — un seul langage de graphique (kit ui/charts) + un seul
// PageHeader ; `ChartEmpty` pour le graphe sans donnée (au lieu d'un <p> nu).
import { BarArrondie, ChartEmpty } from '../ui/charts'
import { PageHeader } from '../ui/PageHeader'
import { formatDateTime, formatNumber } from '../lib/format'
import { downloadBlobInGesture, stampedFilename } from '../utils/downloadBlob'

/* Journal d'activité (Feature G) — réservé au Directeur par défaut
   (permission « journal_activite_voir », octroyable dans Paramètres → Rôles).
   Switcher Jour/Semaine/Mois + barre de filtres pilotant À LA FOIS le graphe
   (recharts, thémé clair/sombre) et la table paginée. Heures en Africa/Casablanca
   (fournies par le serveur).

   YHARD3 — « Historique à cette date » : pour toute entrée reliée à un objet
   (model + object_id connus), un bouton ouvre une reconstruction champ-par-
   champ de l'objet à une date choisie (rejoue les diffs structurés côté
   serveur). Même permission que le reste du Journal (Directeur/admin). */

const PERIODS = [
  { value: 'jour', label: 'Jour' },
  { value: 'semaine', label: 'Semaine' },
  { value: 'mois', label: 'Mois' },
]

// VX236 — Journal menait vers des LISTES NUES (le lien ne portait que la
// route de base, jamais l'objet précis) : chaque entrée devient une FONCTION
// `(objectId) => path`, réutilisant les deep-links déjà posés par VX79/VX22
// (`?lead=`/`?devis=`/`?id=`) — jamais une route inventée. Les modèles sans
// deep-link confirmé (avoir/équipement/produit/admin) retombent sur leur
// route de liste inchangée (comportement identique à avant).
const MODEL_ROUTES = {
  lead: (id) => `/crm/leads?lead=${id}`,
  client: (id) => `/crm?id=${id}`,
  devis: (id) => `/ventes/devis?devis=${id}`,
  facture: (id) => `/ventes/factures?id=${id}`,
  avoir: () => '/ventes/avoirs',
  installation: (id) => `/chantiers?id=${id}`,
  intervention: (id) => `/chantiers?id=${id}`,
  ticket: (id) => `/sav?id=${id}`,
  equipement: () => '/equipements',
  produit: () => '/stock',
  customuser: () => '/admin/users',
  role: () => '/admin/roles',
  companyprofile: () => '/parametres',
}

const todayISO = () => {
  const d = new Date()
  return `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`
}

// Bornes [from, to] (dates ISO) pour la période choisie, autour de `date`.
function periodRange(period, dateStr) {
  const d = new Date(`${dateStr}T00:00:00`)
  const iso = (x) => `${x.getFullYear()}-${String(x.getMonth() + 1).padStart(2, '0')}-${String(x.getDate()).padStart(2, '0')}`
  if (period === 'semaine') {
    const dow = (d.getDay() + 6) % 7 // lundi = 0
    const mon = new Date(d); mon.setDate(d.getDate() - dow)
    const sun = new Date(mon); sun.setDate(mon.getDate() + 6)
    return { from: iso(mon), to: iso(sun) }
  }
  if (period === 'mois') {
    const first = new Date(d.getFullYear(), d.getMonth(), 1)
    const last = new Date(d.getFullYear(), d.getMonth() + 1, 0)
    return { from: iso(first), to: iso(last) }
  }
  return { from: dateStr, to: dateStr }
}

function bucketLabel(period, key) {
  if (period === 'jour') return `${key}h`
  // key = ISO date → jour du mois (mois) ou JJ/MM (semaine).
  const d = new Date(`${key}T00:00:00`)
  if (period === 'semaine') {
    return ['Dim', 'Lun', 'Mar', 'Mer', 'Jeu', 'Ven', 'Sam'][d.getDay()]
  }
  return String(d.getDate())
}

// YHARD3 — bouton + dialog « Historique à cette date » : reconstruction
// champ-par-champ d'un objet à une date choisie (rejoue les diffs structurés
// de AuditLog.changes côté serveur, `apps.audit.selectors.reconstruct_as_of`).
function AsOfDialog({ contentType, objectId, label, open, onOpenChange }) {
  const [date, setDate] = useState(todayISO())
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const [result, setResult] = useState(null)

  useEffect(() => {
    if (!open) return undefined
    let active = true
    const load = async () => {
      setLoading(true); setError(null)
      try {
        const r = await auditApi.getObjectAsOf(contentType, objectId, date)
        if (active) setResult(r.data)
      } catch {
        if (active) setError("Impossible de reconstruire l'historique à cette date.")
      } finally {
        if (active) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [open, contentType, objectId, date])

  const fields = result?.fields ? Object.entries(result.fields) : []

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Historique à cette date — {label}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <label className="flex flex-col gap-1 text-sm" htmlFor="journal-as-of-date">
            Date de référence
            <input
              id="journal-as-of-date"
              type="date"
              value={date}
              onChange={(e) => setDate(e.target.value || todayISO())}
              className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
            />
          </label>

          {loading ? (
            <p className="flex items-center gap-2 py-6 text-sm text-muted-foreground">Chargement…</p>
          ) : error ? (
            <p className="text-sm text-destructive">{error}</p>
          ) : fields.length === 0 ? (
            <EmptyState title="Aucun champ reconstruit"
              description="Aucun historique structuré n'est disponible pour cet objet à cette date."
              className="py-6" />
          ) : (
            <div className="max-w-full overflow-x-auto rounded-lg border border-border">
              <table className="w-full border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Champ</th>
                    <th className="px-3 py-2 text-left text-xs font-semibold text-muted-foreground">Valeur à cette date</th>
                  </tr>
                </thead>
                <tbody>
                  {fields.map(([field, value]) => (
                    <tr key={field} className="border-b border-border/60 last:border-b-0">
                      <td className="px-3 py-2 font-medium text-foreground">{field}</td>
                      <td className="px-3 py-2 text-muted-foreground">{value === null || value === '' ? '—' : String(value)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
        <DialogFooter>
          <DialogClose asChild>
            <Button type="button" variant="outline">Fermer</Button>
          </DialogClose>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
}

function AsOfTrigger({ contentType, objectId, label }) {
  const [open, setOpen] = useState(false)
  return (
    <>
      <IconButton size="sm" variant="ghost" label="Historique à cette date"
        onClick={() => setOpen(true)}>
        <History className="size-4" aria-hidden="true" />
      </IconButton>
      {open && (
        <AsOfDialog contentType={contentType} objectId={objectId} label={label}
          open={open} onOpenChange={setOpen} />
      )}
    </>
  )
}

export default function Journal() {
  const allowed = useHasPermission('journal_activite_voir')

  // VX98 — deep-link « Historique » depuis une fiche : ?model=devis&object_id=42
  // pré-filtre le journal sur CET objet (le backend filtre content_type__model +
  // object_id). Un bouton « Voir tout le journal » retire le filtre.
  const [searchParams, setSearchParams] = useSearchParams()
  const modelParam = searchParams.get('model') || ''
  const objectIdParam = searchParams.get('object_id') || ''
  const clearObjectFilter = () => {
    const next = new URLSearchParams(searchParams)
    next.delete('model'); next.delete('object_id')
    setSearchParams(next, { replace: true })
  }

  const [period, setPeriod] = useState('jour')
  const [date, setDate] = useState(todayISO())
  const [users, setUsers] = useState([])
  const [action, setAction] = useState('')
  const [moduleF, setModuleF] = useState('')
  const [search, setSearch] = useState('')
  const [page, setPage] = useState(1)

  const [meta, setMeta] = useState({ users: [], actions: [], modules: [] })
  const [stats, setStats] = useState(null)
  const [entries, setEntries] = useState(null)
  const [count, setCount] = useState(0)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  // VX204 — un échec de `getMeta()` rendait des menus de filtre vides sans le
  // dire (indiscernable de « aucune valeur possible »).
  const [metaError, setMetaError] = useState(false)

  const range = useMemo(() => periodRange(period, date), [period, date])

  // Filtres communs (graphe + table).
  const filterParams = useMemo(() => {
    const p = {}
    if (users.length) p.user = users
    if (action) p.action = action
    if (moduleF) p.module = moduleF
    if (search.trim()) p.search = search.trim()
    // VX98 — pré-filtre deep-link (fiche → journal sur cet objet).
    if (modelParam) p.model = modelParam
    if (objectIdParam) p.object_id = objectIdParam
    return p
  }, [users, action, moduleF, search, modelParam, objectIdParam])

  // Métadonnées (une fois).
  const loadMeta = () => {
    auditApi.getMeta()
      .then((r) => { setMeta(r.data); setMetaError(false) })
      .catch(() => setMetaError(true))
  }
  useEffect(() => {
    if (!allowed) return
    loadMeta()
  }, [allowed])

  // Graphe + table : période + date + filtres + page. Le setState vit dans une
  // fonction async (jamais synchrone dans le corps de l'effet).
  //
  // ERR69 — un changement de filtre appelle aussi `resetPage()` : `filterParams`
  // ET `page` changent dans le MÊME rendu. Pour ne déclencher QU'UNE seule série
  // de requêtes, on dérive une clé sérialisée stable de toutes les entrées de la
  // requête et on l'utilise comme unique dépendance de l'effet — deux objets
  // `range`/`filterParams` au contenu identique ne re-déclenchent plus rien.
  const requestKey = useMemo(
    () => JSON.stringify({ period, date, range, filterParams, page }),
    [period, date, range, filterParams, page]
  )

  useEffect(() => {
    if (!allowed) return undefined
    let cancelled = false
    const run = async () => {
      setLoading(true)
      setError(null)
      try {
        const [s, e] = await Promise.all([
          auditApi.getStats({ period, date, ...filterParams }),
          auditApi.getEntries({ ...range, ...filterParams, page }),
        ])
        if (cancelled) return
        setStats(s.data)
        setEntries(e.data.results ?? e.data)
        setCount(e.data.count ?? (e.data.results ?? e.data).length)
      } catch {
        if (!cancelled) setError('Impossible de charger le journal.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    run()
    return () => { cancelled = true }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [allowed, requestKey])

  // WIR18/WIR20 — onglets « Sécurité » et « Analytiques », en plus de
  // l'onglet « Activité » historique. Chargés PARESSEUSEMENT (seulement
  // quand l'onglet est actif) : ne pèsent jamais sur le chargement par
  // défaut de l'onglet « Activité » et ne cassent pas les tests existants
  // qui ne mockent que `getStats`/`getEntries`/`getMeta`.
  const [tab, setTab] = useState('activite')
  const isAdmin = useIsAdmin()

  // WIR18 — mêmes filtres que le Journal global (FG23) : période/date +
  // utilisateur(s) + recherche (l'action est fixée au sous-ensemble sécurité
  // côté serveur, le module ne s'applique pas aux évènements de connexion).
  const securityParams = useMemo(() => {
    const p = { ...range }
    if (users.length) p.user = users
    if (search.trim()) p.search = search.trim()
    return p
  }, [range, users, search])

  const [secEvents, setSecEvents] = useState(null)
  const [secLoading, setSecLoading] = useState(false)
  const [secError, setSecError] = useState(null)
  const [secExporting, setSecExporting] = useState(false)

  useEffect(() => {
    if (!allowed || tab !== 'securite') return undefined
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-tab-activate
    setSecLoading(true)
    setSecError(null)
    auditApi.getSecurityEvents(securityParams)
      .then((r) => { if (!cancelled) setSecEvents(r.data.results ?? []) })
      .catch(() => {
        if (!cancelled) setSecError('Impossible de charger les évènements de sécurité.')
      })
      .finally(() => { if (!cancelled) setSecLoading(false) })
    return () => { cancelled = true }
  }, [allowed, tab, securityParams])

  // NTSEC15 — export CSV, gated backend `IsAdminRole` (bouton masqué pour un
  // rôle non-admin ; le serveur re-vérifie de toute façon, 403 sinon).
  const exportSecurityCsv = async () => {
    const pending = downloadBlobInGesture()
    setSecExporting(true)
    try {
      const res = await auditApi.exportSecurityEvents(securityParams)
      pending.deliver(
        new Blob([res.data], { type: 'text/csv' }),
        stampedFilename('securite', 'csv'),
      )
    } catch {
      setSecError('Export indisponible.')
    } finally {
      setSecExporting(false)
    }
  }

  // WIR20 — onglet « Analytiques » : rollups FG97 (top utilisateurs, mix
  // d'actions, activité quotidienne, échecs de connexion) sur la fenêtre
  // par défaut du serveur (30 jours).
  const [analytics, setAnalytics] = useState(null)
  const [analyticsLoading, setAnalyticsLoading] = useState(false)
  const [analyticsError, setAnalyticsError] = useState(null)

  useEffect(() => {
    if (!allowed || tab !== 'analytiques') return undefined
    let cancelled = false
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-tab-activate
    setAnalyticsLoading(true)
    setAnalyticsError(null)
    reportingApi.auditAnalytics()
      .then((r) => { if (!cancelled) setAnalytics(r.data) })
      .catch(() => {
        if (!cancelled) setAnalyticsError("Impossible de charger les analytiques du Journal.")
      })
      .finally(() => { if (!cancelled) setAnalyticsLoading(false) })
    return () => { cancelled = true }
  }, [allowed, tab])

  // Reset de page géré dans les setters de filtres (pas d'effet → pas de
  // cascade de rendus).
  const resetPage = () => setPage(1)
  const onPeriod = (v) => { setPeriod(v); resetPage() }
  const onDate = (v) => { setDate(v || todayISO()); resetPage() }
  const onUsers = (v) => { setUsers(v); resetPage() }
  const onAction = (v) => { setAction(v); resetPage() }
  const onModule = (v) => { setModuleF(v); resetPage() }
  const onSearch = (v) => { setSearch(v); resetPage() }

  if (!allowed) {
    return (
      <div className="ui-root min-h-full p-4 sm:p-6">
        <EmptyState
          title="Accès restreint"
          description="Le Journal d'activité est réservé aux comptes disposant de la permission « Voir le journal » (Directeur par défaut)."
        />
      </div>
    )
  }

  const chartData = (stats?.buckets ?? []).map((b) => ({
    key: b.key, label: bucketLabel(period, b.key), count: b.count,
  }))
  const hasChartData = chartData.some((b) => b.count > 0)
  const pageSize = 100
  const totalPages = Math.max(1, Math.ceil(count / pageSize))

  return (
    <div className="ui-root min-h-full p-4 sm:p-6">
      {/* VX28 — PageHeader unifié (remplace le <h2> nu + sous-titre). */}
      <PageHeader
        title="Journal d'activité"
        subtitle="Qui a fait quoi, et quand — heures en Africa/Casablanca."
      />

      {/* WIR18/WIR20 — Activité (historique) / Sécurité (FG23 + export CSV
          admin) / Analytiques (FG97 : top utilisateurs, mix d'actions,
          activité quotidienne, échecs de connexion). */}
      <Tabs value={tab} onValueChange={setTab}>
        <TabsList className="mb-4">
          <TabsTrigger value="activite">Activité</TabsTrigger>
          <TabsTrigger value="securite">Sécurité</TabsTrigger>
          <TabsTrigger value="analytiques">Analytiques</TabsTrigger>
        </TabsList>

        <TabsContent value="activite">
      {/* VX98 — bandeau « filtré sur cet objet » quand on arrive via le bouton
          « Historique » d'une fiche (?model=&object_id=). */}
      {(modelParam || objectIdParam) && (
        <div className="mb-4 flex flex-wrap items-center justify-between gap-2 rounded-lg border border-primary/30 bg-primary/10 px-3 py-2 text-sm">
          <span className="text-foreground">
            Journal filtré sur {modelParam || 'objet'}
            {objectIdParam ? ` #${objectIdParam}` : ''}
          </span>
          <Button size="sm" variant="outline" onClick={clearObjectFilter}>
            Voir tout le journal
          </Button>
        </div>
      )}

      {/* Switcher période + date */}
      <div className="mb-4 flex flex-wrap items-center gap-3">
        <Segmented options={PERIODS} value={period} onChange={onPeriod} />
        <input
          type="date"
          aria-label="Date de référence"
          value={date}
          onChange={(e) => onDate(e.target.value)}
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      {metaError && (
        <p className="form-error mb-2" role="alert">
          Filtres indisponibles (utilisateurs/actions/modules).{' '}
          <button type="button" className="chatter-retry" onClick={loadMeta}>Réessayer</button>
        </p>
      )}

      {/* Barre de filtres */}
      <div className="mb-4 grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <MultiSelect
          options={meta.users.map((u) => ({ value: String(u.id), label: u.username }))}
          value={users}
          onChange={onUsers}
          placeholder="Tous les utilisateurs"
        />
        <select
          aria-label="Type d'action"
          value={action}
          onChange={(e) => onAction(e.target.value)}
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Toutes les actions</option>
          {meta.actions.map((a) => (
            <option key={a.value} value={a.value}>{a.label}</option>
          ))}
        </select>
        <select
          aria-label="Module"
          value={moduleF}
          onChange={(e) => onModule(e.target.value)}
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        >
          <option value="">Tous les modules</option>
          {meta.modules.map((m) => (
            <option key={m.value} value={m.value}>{m.label}</option>
          ))}
        </select>
        <input
          type="search"
          aria-label="Recherche"
          value={search}
          onChange={(e) => onSearch(e.target.value)}
          placeholder="Rechercher…"
          className="h-[var(--control-h)] rounded-md border border-input bg-card px-[var(--control-px)] text-sm text-foreground shadow-ui-xs focus-visible:border-ring focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
        />
      </div>

      {error ? (
        <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">{error}</CardContent></Card>
      ) : (
        <div className="flex flex-col gap-4">
          {/* Graphe */}
          <Card>
            <CardHeader>
              <CardTitle>
                Activité — {PERIODS.find((p) => p.value === period)?.label}
                {stats ? ` · ${formatNumber(stats.total)} évènement(s)` : ''}
              </CardTitle>
            </CardHeader>
            <CardContent>
              {loading && !stats ? (
                <Skeleton className="h-48 w-full" />
              ) : !hasChartData ? (
                <ChartEmpty title="Aucune activité" description="Aucune activité sur cette période." />
              ) : (
                <BarArrondie
                  data={chartData}
                  dataKey="count"
                  categoryKey="label"
                  tone="primary"
                  name="Évènements"
                  height={220}
                  barSize={period === 'jour' ? 10 : 18}
                  tooltipFormat={(v) => formatNumber(v)}
                />
              )}
            </CardContent>
          </Card>

          {/* Table */}
          <Card className="overflow-hidden">
            <div className="overflow-x-auto">
              <table className="w-full min-w-[640px] border-collapse text-sm">
                <thead>
                  <tr className="border-b border-border bg-muted/40">
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Date / heure</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Utilisateur</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Action</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Objet</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Détail</th>
                    <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Historique</th>
                  </tr>
                </thead>
                <tbody>
                  {loading && !entries ? (
                    Array.from({ length: 6 }).map((u, i) => (
                      <tr key={i} className="border-b border-border/60">
                        <td className="px-4 py-2.5" colSpan={6}><Skeleton className="h-4 w-full" /></td>
                      </tr>
                    ))
                  ) : !entries || entries.length === 0 ? (
                    <tr><td colSpan={6} className="px-4 py-10 text-center text-sm text-muted-foreground">Aucune entrée pour ces filtres.</td></tr>
                  ) : (
                    entries.map((e) => {
                      // VX236 — MODEL_ROUTES est désormais `(objectId) => path` :
                      // le lien pointe sur CET enregistrement précis quand un
                      // deep-link existe, jamais seulement la liste nue.
                      const routeFn = MODEL_ROUTES[e.model]
                      const route = routeFn && e.object_id ? routeFn(e.object_id) : null
                      // YHARD3 — content_type "app_label.model" (`module` sert
                      // en fait l'app_label côté serializer, cf. auditApi).
                      const contentType = e.module && e.model ? `${e.module}.${e.model}` : null
                      return (
                        <tr key={e.id} className="border-b border-border/60 last:border-b-0 hover:bg-accent/40">
                          <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                            {e.timestamp_local ? formatDateTime(e.timestamp_local) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-foreground">{e.utilisateur}</td>
                          <td className="px-4 py-2.5"><Badge tone="info">{e.action_label}</Badge></td>
                          <td className="px-4 py-2.5">
                            {e.object_repr
                              ? (route
                                  ? <Link to={route} className="text-primary hover:underline">{e.object_repr}</Link>
                                  : <span className="text-foreground">{e.object_repr}</span>)
                              : <span className="text-muted-foreground">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-muted-foreground">{e.detail || '—'}</td>
                          <td className="px-4 py-2.5">
                            {contentType && e.object_id ? (
                              <AsOfTrigger contentType={contentType} objectId={e.object_id}
                                label={e.object_repr || `${e.model} #${e.object_id}`} />
                            ) : <span className="text-muted-foreground">—</span>}
                          </td>
                        </tr>
                      )
                    })
                  )}
                </tbody>
              </table>
            </div>
            {count > pageSize && (
              <div className="flex items-center justify-between gap-3 border-t border-border px-4 py-3 text-sm">
                <span className="text-muted-foreground">
                  Page {page} / {totalPages} · {formatNumber(count)} entrées
                </span>
                <div className="flex gap-2">
                  <Button size="sm" variant="outline" disabled={page <= 1} onClick={() => setPage((p) => Math.max(1, p - 1))}>Précédent</Button>
                  <Button size="sm" variant="outline" disabled={page >= totalPages} onClick={() => setPage((p) => p + 1)}>Suivant</Button>
                </div>
              </div>
            )}
          </Card>
        </div>
      )}
        </TabsContent>

        {/* WIR18 — onglet Sécurité (FG23) : connexion/déconnexion/échec/alerte,
            mêmes filtres période/utilisateur/recherche que l'onglet Activité,
            + export CSV réservé aux rôles admin (NTSEC15, gated backend). */}
        <TabsContent value="securite">
          <Card>
            <CardHeader className="flex-row items-center justify-between gap-2">
              <CardTitle>Évènements de sécurité</CardTitle>
              {isAdmin && (
                <Button
                  size="sm"
                  variant="outline"
                  onClick={exportSecurityCsv}
                  disabled={secExporting}
                >
                  <Download className="size-4" aria-hidden="true" />
                  Exporter CSV
                </Button>
              )}
            </CardHeader>
            <CardContent>
              {secError ? (
                <p className="text-sm text-destructive">{secError}</p>
              ) : secLoading && !secEvents ? (
                <Skeleton className="h-48 w-full" />
              ) : !secEvents || secEvents.length === 0 ? (
                <EmptyState
                  title="Aucun évènement"
                  description="Aucun évènement de sécurité pour ces filtres."
                />
              ) : (
                <div className="overflow-x-auto">
                  <table className="w-full min-w-[520px] border-collapse text-sm">
                    <thead>
                      <tr className="border-b border-border bg-muted/40">
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Date / heure</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Utilisateur</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Évènement</th>
                        <th className="px-4 py-2.5 text-left text-xs font-semibold text-muted-foreground">Détail</th>
                      </tr>
                    </thead>
                    <tbody>
                      {secEvents.map((ev) => (
                        <tr key={ev.id} className="border-b border-border/60 last:border-b-0 hover:bg-accent/40">
                          <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                            {ev.timestamp_local ? formatDateTime(ev.timestamp_local) : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-foreground">{ev.utilisateur}</td>
                          <td className="px-4 py-2.5"><Badge tone="info">{ev.action_label}</Badge></td>
                          <td className="px-4 py-2.5 text-muted-foreground">{ev.detail || '—'}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        {/* WIR20 — onglet Analytiques (FG97) : rollups du Journal, fenêtre
            par défaut serveur (30 jours). */}
        <TabsContent value="analytiques">
          {analyticsError ? (
            <Card><CardContent className="py-10 text-center text-sm text-muted-foreground">{analyticsError}</CardContent></Card>
          ) : analyticsLoading && !analytics ? (
            <Skeleton className="h-48 w-full" />
          ) : !analytics ? null : (
            <div className="flex flex-col gap-4">
              <p className="text-sm text-muted-foreground">
                Fenêtre : {analytics.from} → {analytics.to} · {formatNumber(analytics.total_entries)} évènement(s)
              </p>
              <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
                <Card>
                  <CardHeader><CardTitle>Top utilisateurs</CardTitle></CardHeader>
                  <CardContent>
                    {analytics.top_users.length === 0 ? (
                      <ChartEmpty title="Aucune donnée" description="Aucune activité utilisateur sur la période." />
                    ) : (
                      <>
                        {/* WIR20 — résumé texte : la donnée réelle reste visible
                            même si le rendu SVG du graphe est indisponible. */}
                        <p className="mb-2 text-sm text-foreground">
                          Le plus actif : {analytics.top_users[0].actor_username}
                          {' '}({formatNumber(analytics.top_users[0].count)} action(s))
                        </p>
                        <BarArrondie
                          data={analytics.top_users}
                          dataKey="count"
                          categoryKey="actor_username"
                          layout="vertical"
                          tone="primary"
                          name="Actions"
                          height={220}
                        />
                      </>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle>Répartition des actions</CardTitle></CardHeader>
                  <CardContent>
                    {analytics.action_mix.length === 0 ? (
                      <ChartEmpty title="Aucune donnée" description="Aucune action sur la période." />
                    ) : (
                      <>
                        <p className="mb-2 text-sm text-foreground">
                          Action la plus fréquente : {analytics.action_mix[0].label}
                          {' '}({analytics.action_mix[0].pct}%)
                        </p>
                        <BarArrondie
                          data={analytics.action_mix}
                          dataKey="count"
                          categoryKey="label"
                          layout="vertical"
                          tone="info"
                          name="Occurrences"
                          height={220}
                        />
                      </>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle>Activité quotidienne</CardTitle></CardHeader>
                  <CardContent>
                    {analytics.daily_counts.every((d) => d.count === 0) ? (
                      <ChartEmpty title="Aucune activité" description="Aucune activité sur la fenêtre." />
                    ) : (
                      <>
                        <p className="mb-2 text-sm text-foreground">
                          Total sur la fenêtre :{' '}
                          {formatNumber(analytics.daily_counts.reduce((sum, d) => sum + d.count, 0))} évènement(s)
                        </p>
                        <BarArrondie
                          data={analytics.daily_counts}
                          dataKey="count"
                          categoryKey="date"
                          tone="primary"
                          name="Évènements"
                          height={200}
                          barSize={8}
                        />
                      </>
                    )}
                  </CardContent>
                </Card>

                <Card>
                  <CardHeader><CardTitle>Échecs de connexion</CardTitle></CardHeader>
                  <CardContent>
                    {analytics.failed_logins.every((d) => d.count === 0) ? (
                      <ChartEmpty title="Aucun échec" description="Aucun échec de connexion sur la fenêtre." />
                    ) : (
                      <>
                        <p className="mb-2 text-sm text-foreground">
                          Total sur la fenêtre :{' '}
                          {formatNumber(analytics.failed_logins.reduce((sum, d) => sum + d.count, 0))} échec(s)
                        </p>
                        <BarArrondie
                          data={analytics.failed_logins}
                          dataKey="count"
                          categoryKey="date"
                          tone="danger"
                          name="Échecs"
                          height={200}
                          barSize={8}
                        />
                      </>
                    )}
                  </CardContent>
                </Card>
              </div>
            </div>
          )}
        </TabsContent>
      </Tabs>
    </div>
  )
}
