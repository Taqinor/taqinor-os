import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { AlertTriangle, Gauge, Sun } from 'lucide-react'
import monitoringApi from '../../api/monitoringApi'
import { Badge, Card, DataTable, EmptyState, Segmented } from '../../ui'
import { ModuleDashboard } from '../../ui/module'
import { BarArrondie, ChartEmpty } from '../../ui/charts'
import { formatNumber, formatPercent, timeAgo } from '../../lib/format'
import { METRIC_ICONS } from '../../ui/metricIcons'
import MonitoringNav from './MonitoringNav'

/* WR6 — Vue PARC / FLOTTE multi-systèmes (FG281) : production totale, kWc
   installés, PR moyen pondéré et alertes de sous-performance ouvertes sur tous
   les systèmes supervisés de la société, sur une fenêtre glissante.
   VX157 — kWc/production partagent l'icône métier unifiée (ui/metricIcons.js).
   VX30 — mode grille de cartes par installation (bascule avec le tableau via
   Segmented), badge de fraîcheur + auto-poll léger. Le backend
   (`fleet_overview`, apps/monitoring/selectors.py) ne renvoie NI horodatage
   par système NI série temporelle : la fraîcheur est donc suivie au niveau
   PAGE (dernier chargement réussi), pas par carte, et aucune sparkline n'est
   affichée (fabriquer une série factice serait pire que ne rien montrer). */

const WINDOWS = [
  { value: 90, label: '90 j' },
  { value: 180, label: '180 j' },
  { value: 365, label: '1 an' },
]

const VIEW_MODES = [
  { value: 'table', label: 'Tableau' },
  { value: 'grid', label: 'Cartes' },
]

// VX30 — seuils PR à 3 états (vert/orange/rouge) partagés table + grille.
// Un système sans PR calculable (pas de baseline attendue) reste neutre —
// jamais confondu avec une vraie sous-performance.
function prStatus(prPct) {
  if (prPct == null) return 'neutral'
  const v = Number(prPct)
  if (v >= 80) return 'success'
  if (v >= 60) return 'warning'
  return 'danger'
}

// VX30 — sondage 5 min visibility-aware : `useVisibilityAwarePolling` (VX56)
// n'existe pas encore dans ce dépôt (vérifié) ; ce hook local implémente la
// même garde minimale que `useApprobationsCount` (jamais un `setInterval` nu
// qui cogne l'API en onglet caché) et pourra migrer sur VX56 telle quelle.
const FLEET_POLL_MS = 5 * 60 * 1000

function useVisibilityAwarePoll(callback, intervalMs) {
  const cbRef = useRef(callback)
  useEffect(() => { cbRef.current = callback }, [callback])
  useEffect(() => {
    const tick = () => {
      if (typeof document !== 'undefined' && document.visibilityState === 'hidden') return
      cbRef.current()
    }
    const iv = setInterval(tick, intervalMs)
    const onVisible = () => {
      if (document.visibilityState === 'visible') cbRef.current()
    }
    document.addEventListener('visibilitychange', onVisible)
    return () => {
      clearInterval(iv)
      document.removeEventListener('visibilitychange', onVisible)
    }
  }, [intervalMs])
}

export default function FleetPage() {
  const navigate = useNavigate()
  const [fleet, setFleet] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [windowDays, setWindowDays] = useState(365)
  const [viewMode, setViewMode] = useState('table')
  const [lastUpdated, setLastUpdated] = useState(null)
  // VX30 — l'affichage reste celui du DERNIER chargement réussi tant qu'un
  // sondage en arrière-plan échoue (jamais un flash d'EmptyState/erreur sur un
  // simple accroc réseau du polling) ; `stale` distingue « ces chiffres datent »
  // d'un vrai « 0 » (jamais confondus — un système à 0 peut produire ou être
  // en panne, une carte périmée le signale explicitement).
  const [stale, setStale] = useState(false)
  const mountedRef = useRef(true)
  useEffect(() => () => { mountedRef.current = false }, [])

  useEffect(() => {
    let active = true
    const load = async ({ silent = false } = {}) => {
      // setState seulement APRÈS un await (pas de setState synchrone en effet).
      await Promise.resolve()
      if (!active) return
      if (!silent) setLoading(true)
      try {
        const r = await monitoringApi.getFleet({ window_days: windowDays })
        if (active) {
          setFleet(r.data)
          setError(null)
          setStale(false)
          setLastUpdated(new Date())
        }
      } catch {
        if (active) {
          if (silent) {
            // Sondage silencieux en échec : on garde les données affichées
            // mais on les marque explicitement périmées.
            setStale(true)
          } else {
            setError('Impossible de charger la vue parc.')
          }
        }
      } finally {
        if (active && !silent) setLoading(false)
      }
    }
    load()
    return () => { active = false }
  }, [windowDays])

  // VX30 — re-sondage léger 5 min sur l'écran monitoring (silencieux : ne
  // remplace jamais l'état chargé/erreur affiché par un flash de loading).
  useVisibilityAwarePoll(() => {
    monitoringApi.getFleet({ window_days: windowDays })
      .then((r) => {
        if (!mountedRef.current) return
        setFleet(r.data)
        setError(null)
        setStale(false)
        setLastUpdated(new Date())
      })
      .catch(() => { if (mountedRef.current) setStale(true) })
  }, FLEET_POLL_MS)

  const systems = useMemo(() => fleet?.systems ?? [], [fleet])

  const stats = useMemo(() => (fleet ? [
    {
      label: 'Systèmes actifs',
      value: formatNumber(fleet.systems_active),
      icon: Sun,
    },
    {
      label: 'Puissance installée',
      value: `${formatNumber(fleet.total_kwc)} kWc`,
      icon: METRIC_ICONS.kwc,
    },
    {
      label: 'Production (fenêtre)',
      value: `${formatNumber(fleet.total_production_kwh)} kWh`,
      icon: METRIC_ICONS.production,
      hint: `sur ${fleet.window_days ?? windowDays} jours`,
      tone: 'impact',
    },
    {
      label: 'PR parc',
      value: fleet.fleet_pr_pct != null ? formatPercent(fleet.fleet_pr_pct, { decimals: 1 }) : '—',
      icon: Gauge,
      hint: fleet.open_alerts > 0
        ? `${fleet.open_alerts} alerte(s) de sous-performance`
        : 'Aucune alerte ouverte',
    },
  ] : []), [fleet, windowDays])

  const chartData = useMemo(() => systems
    .filter((s) => s.pr_pct != null)
    .map((s) => ({
      label: s.reference || `#${s.installation}`,
      value: Number(s.pr_pct),
    })), [systems])

  const columns = useMemo(() => [
    {
      id: 'reference', header: 'Système',
      accessor: (r) => r.reference || `#${r.installation}`,
    },
    {
      id: 'puissance_kwc', header: 'kWc', width: 110, align: 'right',
      accessor: (r) => Number(r.puissance_kwc) || 0,
      cell: (v, r) => formatNumber(r.puissance_kwc, { decimals: 2 }),
    },
    {
      id: 'production_kwh', header: 'Production (kWh)', width: 160, align: 'right',
      accessor: (r) => Number(r.production_kwh) || 0,
      cell: (v, r) => formatNumber(r.production_kwh, { decimals: 0 }),
    },
    {
      id: 'pr_pct', header: 'PR', width: 120, align: 'right',
      accessor: (r) => (r.pr_pct == null ? -1 : Number(r.pr_pct)),
      cell: (v, r) => (r.pr_pct == null
        ? <span className="text-muted-foreground">—</span>
        : (
          <Badge tone={prStatus(r.pr_pct) === 'neutral' ? 'neutral' : prStatus(r.pr_pct)}>
            {formatPercent(r.pr_pct, { decimals: 1 })}
          </Badge>
        )),
    },
  ], [])

  const goToAnalytics = () => navigate('/production/analytique')

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Vue parc</h1>
        <div className="page-subtitle">
          Production, performance et alertes sur l’ensemble des systèmes supervisés.
        </div>
      </div>
      <MonitoringNav />

      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <div className="flex items-center gap-3">
          <span className="text-sm text-muted-foreground">Fenêtre d’analyse</span>
          <Segmented
            size="sm"
            options={WINDOWS}
            value={windowDays}
            onChange={setWindowDays}
            aria-label="Fenêtre d'analyse"
          />
        </div>
        <div className="flex items-center gap-3">
          {/* VX30 — badge de fraîcheur : distinct visuellement d'un « 0 » de
              production (jamais la même couleur/forme qu'une carte périmée). */}
          {lastUpdated && (
            <span
              className={
                stale
                  ? 'inline-flex items-center gap-1 rounded-full border border-warning/40 bg-warning/10 px-2 py-0.5 text-xs font-medium text-warning'
                  : 'text-xs text-muted-foreground'
              }
            >
              {stale ? 'Hors-ligne — ' : 'Actualisé '}
              {timeAgo(lastUpdated)}
            </span>
          )}
          <Segmented
            size="sm"
            options={VIEW_MODES}
            value={viewMode}
            onChange={setViewMode}
            aria-label="Mode d'affichage"
          />
        </div>
      </div>

      <ModuleDashboard
        stats={stats}
        loading={loading}
        error={error}
        charts={!loading && !error ? [{
          title: 'PR par système (%)',
          span: 'full',
          node: chartData.length > 0
            ? <BarArrondie data={chartData} height={220} name="PR" tooltipFormat={(v) => formatPercent(v, { decimals: 1 })} />
            : <ChartEmpty />,
        }] : []}
      />

      {!loading && !error && (
        systems.length === 0 ? (
          <EmptyState
            icon={AlertTriangle}
            title="Aucun système supervisé"
            description="Configurez la supervision d'un système depuis l'écran Relevés pour le voir apparaître ici."
            className="my-6"
          />
        ) : viewMode === 'grid' ? (
          <div className="mt-6 grid grid-cols-[repeat(auto-fill,minmax(240px,1fr))] gap-4">
            {systems.map((s) => {
              const status = prStatus(s.pr_pct)
              const badgeTone = status === 'neutral' ? 'neutral' : status
              return (
                <Card
                  key={s.installation}
                  className="cursor-pointer p-4 transition-colors hover:border-primary/40"
                  role="button"
                  tabIndex={0}
                  onClick={goToAnalytics}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); goToAnalytics() }
                  }}
                >
                  <div className="flex items-start justify-between gap-2">
                    <span className="font-medium">{s.reference || `#${s.installation}`}</span>
                    <Badge tone={stale ? 'warning' : badgeTone}>
                      {stale ? 'Périmé' : (s.pr_pct == null ? '—' : formatPercent(s.pr_pct, { decimals: 1 }))}
                    </Badge>
                  </div>
                  <div className="mt-3 grid grid-cols-2 gap-2 text-sm">
                    <div>
                      <div className="text-xs text-muted-foreground">kWc</div>
                      <div className="tabular-nums">{formatNumber(s.puissance_kwc, { decimals: 2 })}</div>
                    </div>
                    <div>
                      <div className="text-xs text-muted-foreground">Production</div>
                      <div className="tabular-nums">{formatNumber(s.production_kwh, { decimals: 0 })} kWh</div>
                    </div>
                  </div>
                </Card>
              )
            })}
          </div>
        ) : (
          <div className="mt-6">
            <DataTable
              data={systems}
              columns={columns}
              getRowId={(row) => row.installation}
              searchable={false}
              pageSize={25}
              aria-label="Systèmes du parc"
            />
          </div>
        )
      )}
    </div>
  )
}
