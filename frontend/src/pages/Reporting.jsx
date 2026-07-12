import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import { useNavigate } from 'react-router-dom'
import {
  RefreshCw, Wallet, Clock, Users, Package, BarChart3, AlertTriangle, Download,
} from 'lucide-react'
import {
  PieChart, Pie, Cell, Tooltip, ResponsiveContainer, Legend,
  AreaChart, Area, XAxis, YAxis, CartesianGrid,
} from 'recharts'
import { fetchDashboard } from '../features/reporting/store/reportingSlice'
import reportingApi from '../api/reportingApi'
import api from '../api/axios'
import { downloadXlsx } from '../api/importApi'
import { formatMAD, formatNumber, formatPercent, toNumber } from '../lib/format'
import {
  Button, Card, CardHeader, CardTitle, CardContent, CardDescription,
  Stat, Badge, StatusPill, Segmented, Skeleton, EmptyState, Progress,
} from '../ui'
// VX28 — un seul langage de graphique (kit ui/charts) + un seul PageHeader.
// Le camembert « Répartition des factures » reste en recharts natif (le kit ne
// fournit pas de primitive Pie) ; l'aire CA et les barres top-produits passent
// au kit.
import {
  AreaSansAxe, BarArrondie, ChartTooltip,
  CHART_TOKENS, CHART_GRID_STYLE, CHART_COMPARISON_STYLE, categoricalColor,
  animationDuration, CHART_ANIM_EASING,
} from '../ui/charts'
import { PageHeader } from '../ui/PageHeader'
import { Table } from './reporting/Table'

// ── Formatage monétaire (DH, sans décimales — comme l'écran historique) ──────
// K149 — toutes les figures passent par les utilitaires F19 (Intl fr-MA / MAD).
const dh = (v) => formatMAD(v, { decimals: 0 }).replace(' MAD', ' DH')

// K149 — Montant COMPACT pour les tuiles KPI (« 1,2 M DH », « 320 k DH »).
// Notation compacte fr-MA + suffixe DH ; tiret cadratin si valeur invalide.
const dhCompact = (v) => {
  const n = toNumber(v)
  if (n === null) return '—'
  const body = new Intl.NumberFormat('fr-MA', {
    notation: 'compact',
    maximumFractionDigits: 1,
  }).format(n)
  return `${body} DH`
}

// VX28 — le camembert « Répartition des factures » reste en recharts natif
// (aucune primitive Pie dans le kit) ; il garde son style d'infobulle tokenisé.
const CHART_TOOLTIP_STYLE = {
  borderRadius: 8,
  fontSize: 12,
  background: 'var(--color-popover)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-popover-foreground)',
}

// ── Barre de conversion (J146 — composant Progress partagé) ──────────────────
function ConversionBar({ label, value, max, tone }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between text-sm text-muted-foreground">
        <span>{label}</span>
        <span className="font-semibold tabular-nums text-foreground">
          {formatNumber(value)}{' '}
          <span className="font-normal text-muted-foreground">({formatPercent(pct)})</span>
        </span>
      </div>
      <Progress value={pct} tone={tone} />
    </div>
  )
}

// ── Valeur du pipeline (T7) — section auto-chargée (lecture seule) ───────────
function StageTable({ title, rows, keyField, labelField }) {
  // J146 — migré vers le primitif Table partagé (plus de <table data-table>).
  // L878 — le primitif enveloppe toujours sa table d'un conteneur scrollable.
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <Table
        aria-label={title}
        getRowKey={(s) => s[keyField]}
        columns={[
          { key: labelField, cell: (s) => s[labelField] },
          { key: 'count', align: 'right', cellClassName: 'text-muted-foreground', cell: (s) => formatNumber(s.count) },
          { key: 'valeur', align: 'right', cellClassName: 'font-semibold', cell: (s) => dh(s.valeur) },
        ]}
        rows={rows}
      />
    </div>
  )
}

function PipelineSection() {
  const [p, setP] = useState(null)
  // 'loading' | 'ok' | 'error' — distingue le chargement d'un échec de fetch.
  const [phase, setPhase] = useState('loading')
  useEffect(() => {
    reportingApi.getPipeline()
      .then((r) => { setP(r.data); setPhase('ok') })
      .catch(() => { setP(null); setPhase('error') })
  }, [])
  if (phase === 'error') {
    return (
      <Card className="mb-6">
        <CardHeader><CardTitle>Valeur du pipeline</CardTitle></CardHeader>
        <CardContent>
          <p className="text-sm text-destructive">
            Valeur du pipeline indisponible
          </p>
        </CardContent>
      </Card>
    )
  }
  if (!p) return null

  return (
    <Card className="mb-6">
      <CardHeader>
        <CardTitle>Valeur du pipeline</CardTitle>
        <CardDescription>
          Prévision pondérée : <strong className="text-foreground tabular-nums">{dh(p.prevision_ponderee)}</strong>
          {' · '}Gagnés : <strong className="text-foreground tabular-nums">{formatNumber(p.gagnes.count)}</strong>{' '}
          ({dh(p.gagnes.valeur)})
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-5 md:grid-cols-2">
          <StageTable title="Par étape" rows={p.par_etape} keyField="stage" labelField="label" />
          <div className="space-y-4">
            <StageTable title="Devis par statut" rows={p.devis_par_statut} keyField="statut" labelField="label" />
            {p.perdus_par_motif.length > 0 && (
              <div>
                <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                  Pertes par motif
                </div>
                <Table
                  aria-label="Pertes par motif"
                  getRowKey={(m) => m.motif}
                  columns={[
                    { key: 'motif', cell: (m) => m.motif },
                    { key: 'count', align: 'right', cellClassName: 'text-muted-foreground', cell: (m) => formatNumber(m.count) },
                    { key: 'valeur', align: 'right', cell: (m) => dh(m.valeur) },
                  ]}
                  rows={p.perdus_par_motif}
                />
              </div>
            )}
          </div>
        </div>
      </CardContent>
    </Card>
  )
}

// ── Squelette de chargement ──────────────────────────────────────────────────
function LoadingState() {
  return (
    <div className="space-y-6">
      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        {Array.from({ length: 4 }).map((unused, i) => (
          <Card key={i} className="p-4 sm:p-5">
            <Skeleton className="h-3 w-1/2" />
            <Skeleton className="mt-3 h-7 w-2/3" />
            <Skeleton className="mt-2 h-3 w-1/3" />
          </Card>
        ))}
      </div>
      <div className="grid gap-4 lg:grid-cols-2">
        {Array.from({ length: 2 }).map((unused, i) => (
          <Card key={i}>
            <CardHeader><Skeleton className="h-4 w-1/3" /></CardHeader>
            <CardContent><Skeleton className="h-52 w-full" /></CardContent>
          </Card>
        ))}
      </div>
    </div>
  )
}

// KPI cliquable : ouvre la liste des enregistrements correspondants au lieu de
// rester un compteur sans issue.
function ClickableStat({ to, navigate, ...props }) {
  return (
    <Stat
      {...props}
      role="button"
      tabIndex={0}
      className="cursor-pointer transition-colors hover:border-primary/40"
      onClick={() => navigate(to)}
      onKeyDown={(e) => {
        if (e.key === 'Enter' || e.key === ' ') {
          e.preventDefault()
          navigate(to)
        }
      }}
    />
  )
}

export function Component() {
  const dispatch = useDispatch()
  const navigate = useNavigate()
  const { data, loading, error } = useSelector((s) => s.reporting)

  // Fenêtre d'affichage du CA mensuel (filtrage CLIENT sur les données déjà
  // chargées — aucun appel API supplémentaire, comportement inchangé).
  const [caWindowMonths, setCaWindowMonths] = useState('12')
  // VX41 — comparaison togglable « période précédente » (off par défaut).
  const [caCompare, setCaCompare] = useState(false)

  useEffect(() => {
    dispatch(fetchDashboard())
  }, [dispatch])

  const caWindow = useMemo(() => {
    if (!data?.ca_mensuel) return []
    const n = caWindowMonths === 'all' ? data.ca_mensuel.length : Number(caWindowMonths)
    return data.ca_mensuel.slice(-n)
  }, [data, caWindowMonths])

  // VX41 — la comparaison n'est honnête que pour la fenêtre 6 mois : le
  // backend `_ca_mensuel` renvoie toujours exactement 12 mois calendaires
  // (voir apps/reporting/views.py), donc les 6 mois qui précèdent la fenêtre
  // affichée existent déjà dans `data.ca_mensuel` — zéro appel API. Pour les
  // fenêtres 12 mois/Tout, il n'existe PAS de 12 mois précédents chargés :
  // on masque le bascule plutôt que d'inventer une donnée (checked-facts-only).
  const caCompareAvailable = caWindowMonths === '6' && (data?.ca_mensuel?.length ?? 0) >= 12
  const caWindowCompare = useMemo(() => {
    if (!caCompareAvailable) return []
    const precedent = data.ca_mensuel.slice(0, 6)
    return caWindow.map((m, i) => ({ ...m, caPrecedent: precedent[i]?.ca ?? 0 }))
  }, [caWindow, caCompareAvailable, data])

  // Export .xlsx (KPIs + créances clients), scopé société côté serveur.
  const exportDashboard = () => api
    .get('/reporting/dashboard/', { params: { export: 'xlsx' }, responseType: 'blob' })
    .then((r) => downloadXlsx(r.data, 'reporting-dashboard.xlsx'))
    .catch(() => {})

  if (loading) {
    return (
      <div className="ui-root page" style={{ maxWidth: 1200 }}>
        {/* VX28 — PageHeader unifié. */}
        <PageHeader title="Reporting & Analytics" icon={BarChart3} />
        <LoadingState />
      </div>
    )
  }

  if (error) {
    return (
      <div className="ui-root page" style={{ maxWidth: 1200 }}>
        {/* VX28 — PageHeader unifié. */}
        <PageHeader title="Reporting & Analytics" icon={BarChart3} />
        <EmptyState
          icon={AlertTriangle}
          title="Données indisponibles"
          description={error}
          action={<Button onClick={() => dispatch(fetchDashboard())}><RefreshCw /> Réessayer</Button>}
        />
      </div>
    )
  }

  if (!data) return null

  const {
    kpis = {},
    top_produits = [],
    statuts_factures = [],
    conversion = {},
    stock_alerte = [],
    creances = [],
  } = data
  const caVide = caWindow.every((m) => m.ca === 0)

  return (
    <div className="ui-root page" style={{ maxWidth: 1200 }}>
      {/* VX28 — PageHeader unifié : titre + actions (export/actualiser). */}
      <PageHeader
        title="Reporting & Analytics"
        icon={BarChart3}
        actions={(
          <>
            <Button variant="outline" size="sm" onClick={exportDashboard}>
              <Download /> Exporter Excel
            </Button>
            <Button variant="outline" size="sm" onClick={() => dispatch(fetchDashboard())}>
              <RefreshCw /> Actualiser
            </Button>
          </>
        )}
      />

      <PipelineSection />

      {/* ── KPIs ── */}
      <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <ClickableStat navigate={navigate} to="/ventes/factures?statut=payee" label="CA encaissé" value={dhCompact(kpis.ca_paye)} hint="Factures payées" icon={Wallet} />
        <ClickableStat navigate={navigate} to="/ventes/factures?statut=en_retard" label="En attente de paiement" value={dhCompact(kpis.ca_attente)} hint="Émises + en retard" icon={Clock} />
        <ClickableStat navigate={navigate} to="/crm" label="Clients actifs" value={formatNumber(kpis.nb_clients)} hint="Total base clients" icon={Users} />
        <ClickableStat navigate={navigate} to="/stock" label="Valeur du stock" value={dhCompact(kpis.valeur_stock)} hint="Prix vente × quantité" icon={Package} />
      </div>

      {/* ── Graphiques ligne 1 ── */}
      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        {/* CA mensuel */}
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3">
            <CardTitle>CA mensuel</CardTitle>
            <div className="flex items-center gap-2">
              {/* VX41 — comparaison « période précédente », uniquement quand la
                  fenêtre 6 mois laisse assez d'historique déjà chargé pour
                  l'afficher honnêtement (voir caCompareAvailable). */}
              {caCompareAvailable && (
                <Segmented
                  size="sm"
                  value={caCompare ? 'compare' : 'simple'}
                  onChange={(v) => setCaCompare(v === 'compare')}
                  options={[
                    { value: 'simple', label: 'CA seul' },
                    { value: 'compare', label: 'Vs période précédente' },
                  ]}
                />
              )}
              <Segmented
                size="sm"
                value={caWindowMonths}
                onChange={setCaWindowMonths}
                options={[
                  { value: '6', label: '6 mois' },
                  { value: '12', label: '12 mois' },
                  { value: 'all', label: 'Tout' },
                ]}
              />
            </div>
          </CardHeader>
          <CardContent>
            {caVide ? (
              <EmptyState
                icon={BarChart3}
                title="Aucune facture payée"
                description="Aucune facture payée sur la période sélectionnée."
                className="border-0 py-8"
              />
            ) : caCompare && caCompareAvailable ? (
              <>
                <ResponsiveContainer width="100%" height={220}>
                  <AreaChart data={caWindowCompare} margin={{ top: 8, right: 8, bottom: 0, left: 0 }}>
                    <CartesianGrid {...CHART_GRID_STYLE} />
                    <XAxis
                      dataKey="mois"
                      tick={{ fontSize: 11, fill: CHART_TOKENS.axis }}
                      tickLine={false}
                      axisLine={false}
                    />
                    <YAxis hide domain={[0, 'auto']} />
                    <Tooltip
                      cursor={{ stroke: CHART_TOKENS.grid }}
                      content={<ChartTooltip format={(v) => dh(v)} />}
                    />
                    <Area
                      type="monotone"
                      dataKey="ca"
                      name="CA HT (période actuelle)"
                      stroke={categoricalColor(0)}
                      strokeWidth={2}
                      fill={categoricalColor(0)}
                      fillOpacity={0.12}
                      dot={false}
                      isAnimationActive={animationDuration() > 0}
                      animationDuration={animationDuration()}
                      animationEasing={CHART_ANIM_EASING}
                    />
                    <Area
                      type="monotone"
                      dataKey="caPrecedent"
                      name="CA HT (période précédente)"
                      stroke={categoricalColor(1)}
                      dot={false}
                      isAnimationActive={animationDuration() > 0}
                      animationDuration={animationDuration()}
                      animationEasing={CHART_ANIM_EASING}
                      {...CHART_COMPARISON_STYLE}
                    />
                  </AreaChart>
                </ResponsiveContainer>
                <div className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-xs text-muted-foreground">
                  <span className="inline-flex items-center gap-1.5">
                    <span aria-hidden="true" className="inline-block h-0.5 w-3.5 rounded-full" style={{ background: categoricalColor(0) }} />
                    Période actuelle
                  </span>
                  <span className="inline-flex items-center gap-1.5">
                    <span
                      aria-hidden="true"
                      className="inline-block h-0.5 w-3.5"
                      style={{
                        backgroundImage: `repeating-linear-gradient(90deg, ${categoricalColor(1)} 0 4px, transparent 4px 7px)`,
                      }}
                    />
                    Période précédente
                  </span>
                </div>
              </>
            ) : (
              <AreaSansAxe
                data={caWindow}
                dataKey="ca"
                xKey="mois"
                tone="info"
                name="CA HT"
                height={220}
                tooltipFormat={(v) => dh(v)}
              />
            )}
          </CardContent>
        </Card>

        {/* Top produits */}
        <Card>
          <CardHeader><CardTitle>Top 5 produits vendus (quantité)</CardTitle></CardHeader>
          <CardContent>
            {top_produits.length === 0 ? (
              <EmptyState
                icon={Package}
                title="Aucune vente"
                description="Aucune vente enregistrée."
                className="border-0 py-8"
              />
            ) : (
              <BarArrondie
                data={top_produits}
                dataKey="qte"
                categoryKey="nom"
                layout="vertical"
                tone="primary"
                name="Qté vendue"
                height={220}
                categoryWidth={100}
                tooltipFormat={(v) => `${formatNumber(v)} unités`}
              />
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Graphiques ligne 2 ── */}
      <div className="mb-4 grid gap-4 lg:grid-cols-3">
        {/* Statuts factures */}
        <Card>
          <CardHeader><CardTitle>Répartition des factures</CardTitle></CardHeader>
          <CardContent>
            {statuts_factures.length === 0 ? (
              <EmptyState icon={BarChart3} title="Aucune facture" className="border-0 py-8" />
            ) : (
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={statuts_factures}
                    cx="50%" cy="50%"
                    innerRadius={55} outerRadius={80}
                    paddingAngle={3}
                    dataKey="value"
                  >
                    {statuts_factures.map((entry, i) => (
                      <Cell key={i} fill={entry.color} />
                    ))}
                  </Pie>
                  <Tooltip
                    formatter={(v, n) => [formatNumber(v), n]}
                    contentStyle={CHART_TOOLTIP_STYLE}
                  />
                  <Legend iconType="circle" iconSize={10} wrapperStyle={{ fontSize: 12 }} />
                </PieChart>
              </ResponsiveContainer>
            )}
          </CardContent>
        </Card>

        {/* Conversion */}
        <Card>
          <CardHeader><CardTitle>Tunnel de conversion</CardTitle></CardHeader>
          <CardContent>
            <ConversionBar label="Devis créés" value={conversion.nb_devis} max={conversion.nb_devis} tone="info" />
            <ConversionBar label="Devis acceptés" value={conversion.nb_acceptes} max={conversion.nb_devis} tone="success" />
            <ConversionBar label="Factures émises" value={conversion.nb_factures} max={conversion.nb_devis} tone="primary" />
            {conversion.nb_devis > 0 && (
              <div className="mt-4 rounded-lg bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                Taux de conversion global :{' '}
                <strong className="tabular-nums text-foreground">
                  {formatPercent(Math.round((conversion.nb_factures / conversion.nb_devis) * 100))}
                </strong>
              </div>
            )}
          </CardContent>
        </Card>

        {/* Stock critique */}
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-2">
            <CardTitle>Stock sous seuil d'alerte</CardTitle>
            <Badge tone={stock_alerte.length > 0 ? 'warning' : 'success'}>{stock_alerte.length}</Badge>
          </CardHeader>
          <CardContent>
            {stock_alerte.length === 0 ? (
              <EmptyState
                icon={Package}
                title="Stocks au-dessus du seuil"
                description="Tous les stocks sont au-dessus du seuil."
                className="border-0 py-6"
              />
            ) : (
              <div className="flex flex-col gap-1.5">
                {stock_alerte.map((p, i) => {
                  const rupture = p.quantite_stock <= 0
                  return (
                    <div
                      key={i}
                      className={`flex items-center justify-between gap-2 rounded-lg border px-3 py-2 text-sm ${
                        rupture ? 'border-destructive/30 bg-destructive/10' : 'border-warning/30 bg-warning/10'
                      }`}
                    >
                      <span className="min-w-0 flex-1 truncate font-medium text-foreground">{p.nom}</span>
                      <StatusPill
                        tone={rupture ? 'danger' : 'warning'}
                        dot={false}
                        label={rupture ? 'Rupture' : `${p.quantite_stock} / ${p.seuil_alerte}`}
                      />
                    </div>
                  )
                })}
              </div>
            )}
          </CardContent>
        </Card>
      </div>

      {/* ── Créances clients ── */}
      {creances.length > 0 && (
        <Card className="mb-4">
          <CardHeader><CardTitle>Créances clients (factures impayées)</CardTitle></CardHeader>
          <CardContent>
            <Table
              aria-label="Créances clients"
              columns={[
                { key: 'client', header: 'Client', cellClassName: 'font-medium', cell: (c) => c.client },
                { key: 'nb_factures', header: 'Nb factures', align: 'right', cellClassName: 'text-muted-foreground', cell: (c) => formatNumber(c.nb_factures) },
                { key: 'montant_total', header: 'Montant total', align: 'right', cellClassName: 'font-semibold text-destructive', cell: (c) => dh(c.montant_total) },
                {
                  key: 'jours_retard_max',
                  header: 'Retard max',
                  align: 'right',
                  cell: (c) => (c.jours_retard_max > 0
                    ? <StatusPill tone="danger" dot={false} label={`${c.jours_retard_max} j`} />
                    : <span className="text-muted-foreground">—</span>),
                },
              ]}
              rows={creances}
            />
          </CardContent>
        </Card>
      )}
    </div>
  )
}
