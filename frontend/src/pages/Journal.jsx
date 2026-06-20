import { useEffect, useMemo, useState } from 'react'
import { useSelector } from 'react-redux'
import { Link } from 'react-router-dom'
import {
  BarChart, Bar, XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer,
} from 'recharts'
import auditApi from '../api/auditApi'
import {
  Card, CardHeader, CardTitle, CardContent, Segmented, MultiSelect,
  Button, Badge, Skeleton, EmptyState,
} from '../ui'
import { formatNumber } from '../lib/format'

/* Journal d'activité (Feature G) — réservé au Directeur par défaut
   (permission « journal_activite_voir », octroyable dans Paramètres → Rôles).
   Switcher Jour/Semaine/Mois + barre de filtres pilotant À LA FOIS le graphe
   (recharts, thémé clair/sombre) et la table paginée. Heures en Africa/Casablanca
   (fournies par le serveur). */

const TOKEN = {
  primary: 'var(--primary)',
  muted: 'var(--muted-foreground)',
  grid: 'var(--border)',
  surface: 'var(--popover)',
}

const tooltipStyle = {
  borderRadius: 10,
  fontSize: 12,
  border: `1px solid ${TOKEN.grid}`,
  background: TOKEN.surface,
  color: 'var(--popover-foreground)',
  boxShadow: 'var(--shadow-md)',
}

const PERIODS = [
  { value: 'jour', label: 'Jour' },
  { value: 'semaine', label: 'Semaine' },
  { value: 'mois', label: 'Mois' },
]

// Modèle → route de liste (lien retour « au mieux »).
const MODEL_ROUTES = {
  lead: '/crm/leads',
  client: '/crm',
  devis: '/ventes/devis',
  facture: '/ventes/factures',
  avoir: '/ventes/avoirs',
  installation: '/chantiers',
  intervention: '/chantiers',
  ticket: '/sav',
  equipement: '/equipements',
  produit: '/stock',
  customuser: '/admin/users',
  role: '/admin/roles',
  companyprofile: '/parametres',
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

export default function Journal() {
  const permissions = useSelector((s) => s.auth.permissions) || []
  const allowed = permissions.includes('journal_activite_voir')

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

  const range = useMemo(() => periodRange(period, date), [period, date])

  // Filtres communs (graphe + table).
  const filterParams = useMemo(() => {
    const p = {}
    if (users.length) p.user = users
    if (action) p.action = action
    if (moduleF) p.module = moduleF
    if (search.trim()) p.search = search.trim()
    return p
  }, [users, action, moduleF, search])

  // Métadonnées (une fois).
  useEffect(() => {
    if (!allowed) return
    auditApi.getMeta().then((r) => setMeta(r.data)).catch(() => {})
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
      <header className="mb-5">
        <h2 className="font-display text-xl font-bold tracking-tight text-foreground">
          Journal d'activité
        </h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Qui a fait quoi, et quand — heures en Africa/Casablanca.
        </p>
      </header>

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
                <p className="py-8 text-center text-sm text-muted-foreground">
                  Aucune activité sur cette période.
                </p>
              ) : (
                <ResponsiveContainer width="100%" height={220}>
                  <BarChart data={chartData} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid strokeDasharray="3 3" stroke={TOKEN.grid} vertical={false} />
                    <XAxis dataKey="label" tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} interval="preserveStartEnd" />
                    <YAxis allowDecimals={false} width={32} tick={{ fontSize: 11, fill: TOKEN.muted }} tickLine={false} axisLine={false} />
                    <Tooltip cursor={{ fill: 'var(--muted)' }} contentStyle={tooltipStyle} formatter={(v) => [formatNumber(v), 'Évènements']} />
                    <Bar dataKey="count" radius={[4, 4, 0, 0]} fill={TOKEN.primary} barSize={period === 'jour' ? 10 : 18} />
                  </BarChart>
                </ResponsiveContainer>
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
                  </tr>
                </thead>
                <tbody>
                  {loading && !entries ? (
                    Array.from({ length: 6 }).map((u, i) => (
                      <tr key={i} className="border-b border-border/60">
                        <td className="px-4 py-2.5" colSpan={5}><Skeleton className="h-4 w-full" /></td>
                      </tr>
                    ))
                  ) : !entries || entries.length === 0 ? (
                    <tr><td colSpan={5} className="px-4 py-10 text-center text-sm text-muted-foreground">Aucune entrée pour ces filtres.</td></tr>
                  ) : (
                    entries.map((e) => {
                      const route = MODEL_ROUTES[e.model]
                      return (
                        <tr key={e.id} className="border-b border-border/60 last:border-b-0 hover:bg-accent/40">
                          <td className="px-4 py-2.5 whitespace-nowrap text-muted-foreground">
                            {e.timestamp_local ? new Date(e.timestamp_local).toLocaleString('fr-FR') : '—'}
                          </td>
                          <td className="px-4 py-2.5 text-foreground">{e.utilisateur}</td>
                          <td className="px-4 py-2.5"><Badge tone="info">{e.action_label}</Badge></td>
                          <td className="px-4 py-2.5">
                            {e.object_repr
                              ? (route && e.object_id
                                  ? <Link to={route} className="text-primary hover:underline">{e.object_repr}</Link>
                                  : <span className="text-foreground">{e.object_repr}</span>)
                              : <span className="text-muted-foreground">—</span>}
                          </td>
                          <td className="px-4 py-2.5 text-muted-foreground">{e.detail || '—'}</td>
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
    </div>
  )
}
