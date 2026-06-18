import { useEffect, useMemo, useState } from 'react'
import { useDispatch, useSelector } from 'react-redux'
import {
  RefreshCw, Wallet, Clock, Users, Package, BarChart3, AlertTriangle,
} from 'lucide-react'
import {
  AreaChart, Area, BarChart, Bar, PieChart, Pie, Cell,
  XAxis, YAxis, CartesianGrid, Tooltip, ResponsiveContainer, Legend,
} from 'recharts'
import { fetchDashboard } from '../features/reporting/store/reportingSlice'
import reportingApi from '../api/reportingApi'
import { formatMAD, formatNumber } from '../lib/format'
import {
  Button, Card, CardHeader, CardTitle, CardContent, CardDescription,
  Stat, Badge, StatusPill, Segmented, Skeleton, EmptyState,
} from '../ui'

// ── Formatage monétaire (DH, sans décimales — comme l'écran historique) ──────
const dh = (v) => formatMAD(v, { decimals: 0 }).replace(' MAD', ' DH')

// Couleurs de séries pour recharts, tirées des tokens sémantiques (clair/sombre).
const CHART_INFO = 'var(--color-info)'
const CHART_PRIMARY = 'var(--color-primary)'
const CHART_GRID = 'var(--color-border)'
const CHART_AXIS = 'var(--color-muted-foreground)'
const CHART_TOOLTIP_STYLE = {
  borderRadius: 8,
  fontSize: 12,
  background: 'var(--color-popover)',
  border: '1px solid var(--color-border)',
  color: 'var(--color-popover-foreground)',
}

// ── Tooltip recharts thémé via tokens ───────────────────────────────────────
function TooltipDH({ active, payload, label }) {
  if (!active || !payload?.length) return null
  return (
    <div className="rounded-md border border-border bg-popover px-3 py-2 text-xs text-popover-foreground shadow-ui-md">
      <div className="mb-1 font-semibold">{label}</div>
      {payload.map((p, i) => (
        <div key={i} className="tabular-nums" style={{ color: p.color ?? CHART_INFO }}>
          {p.name ?? 'CA'} : {dh(p.value)}
        </div>
      ))}
    </div>
  )
}

// ── Barre de conversion (token-themed) ───────────────────────────────────────
function ConversionBar({ label, value, max, tone }) {
  const pct = max > 0 ? Math.round((value / max) * 100) : 0
  return (
    <div className="mb-3">
      <div className="mb-1 flex items-center justify-between text-sm text-muted-foreground">
        <span>{label}</span>
        <span className="font-semibold tabular-nums text-foreground">
          {formatNumber(value)} <span className="font-normal text-muted-foreground">({pct}%)</span>
        </span>
      </div>
      <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
        <div
          className={tone}
          style={{ width: `${pct}%`, height: '100%', borderRadius: 9999, transition: 'width 0.6s ease' }}
        />
      </div>
    </div>
  )
}

// ── Valeur du pipeline (T7) — section auto-chargée (lecture seule) ───────────
function StageTable({ title, rows, keyField, labelField }) {
  return (
    <div>
      <div className="mb-1.5 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
        {title}
      </div>
      <table className="data-table">
        <tbody>
          {rows.map((s) => (
            <tr key={s[keyField]}>
              <td>{s[labelField]}</td>
              <td className="ta-right text-muted-foreground tabular-nums">{formatNumber(s.count)}</td>
              <td className="ta-right font-semibold tabular-nums">{dh(s.valeur)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

function PipelineSection() {
  const [p, setP] = useState(null)
  useEffect(() => {
    reportingApi.getPipeline().then((r) => setP(r.data)).catch(() => setP(null))
  }, [])
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
                <table className="data-table">
                  <tbody>
                    {p.perdus_par_motif.map((m) => (
                      <tr key={m.motif}>
                        <td>{m.motif}</td>
                        <td className="ta-right text-muted-foreground tabular-nums">{formatNumber(m.count)}</td>
                        <td className="ta-right tabular-nums">{dh(m.valeur)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
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

export function Component() {
  const dispatch = useDispatch()
  const { data, loading, error } = useSelector((s) => s.reporting)

  // Fenêtre d'affichage du CA mensuel (filtrage CLIENT sur les données déjà
  // chargées — aucun appel API supplémentaire, comportement inchangé).
  const [caWindowMonths, setCaWindowMonths] = useState('12')

  useEffect(() => {
    dispatch(fetchDashboard())
  }, [dispatch])

  const caWindow = useMemo(() => {
    if (!data?.ca_mensuel) return []
    const n = caWindowMonths === 'all' ? data.ca_mensuel.length : Number(caWindowMonths)
    return data.ca_mensuel.slice(-n)
  }, [data, caWindowMonths])

  if (loading) {
    return (
      <div className="ui-root page" style={{ maxWidth: 1200 }}>
        <div className="page-header" style={{ marginBottom: '1.5rem' }}>
          <h2>Reporting &amp; Analytics</h2>
        </div>
        <LoadingState />
      </div>
    )
  }

  if (error) {
    return (
      <div className="ui-root page" style={{ maxWidth: 1200 }}>
        <div className="page-header" style={{ marginBottom: '1.5rem' }}>
          <h2>Reporting &amp; Analytics</h2>
        </div>
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

  const { kpis, top_produits, statuts_factures, conversion, stock_alerte, creances } = data
  const caVide = caWindow.every((m) => m.ca === 0)

  return (
    <div className="ui-root page" style={{ maxWidth: 1200 }}>
      <div className="page-header" style={{ marginBottom: '1.5rem' }}>
        <h2>Reporting &amp; Analytics</h2>
        <Button variant="outline" size="sm" onClick={() => dispatch(fetchDashboard())}>
          <RefreshCw /> Actualiser
        </Button>
      </div>

      <PipelineSection />

      {/* ── KPIs ── */}
      <div className="mb-7 grid gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Stat label="CA encaissé" value={dh(kpis.ca_paye)} hint="Factures payées" icon={Wallet} />
        <Stat label="En attente de paiement" value={dh(kpis.ca_attente)} hint="Émises + en retard" icon={Clock} />
        <Stat label="Clients actifs" value={formatNumber(kpis.nb_clients)} hint="Total base clients" icon={Users} />
        <Stat label="Valeur du stock" value={dh(kpis.valeur_stock)} hint="Prix vente × quantité" icon={Package} />
      </div>

      {/* ── Graphiques ligne 1 ── */}
      <div className="mb-4 grid gap-4 lg:grid-cols-2">
        {/* CA mensuel */}
        <Card>
          <CardHeader className="flex-row items-center justify-between gap-3">
            <CardTitle>CA mensuel</CardTitle>
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
          </CardHeader>
          <CardContent>
            {caVide ? (
              <EmptyState
                icon={BarChart3}
                title="Aucune facture payée"
                description="Aucune facture payée sur la période sélectionnée."
                className="border-0 py-8"
              />
            ) : (
              <ResponsiveContainer width="100%" height={220}>
                <AreaChart data={caWindow} margin={{ top: 4, right: 4, bottom: 0, left: 0 }}>
                  <defs>
                    <linearGradient id="caGradient" x1="0" y1="0" x2="0" y2="1">
                      <stop offset="5%" stopColor={CHART_INFO} stopOpacity={0.2} />
                      <stop offset="95%" stopColor={CHART_INFO} stopOpacity={0} />
                    </linearGradient>
                  </defs>
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} />
                  <XAxis dataKey="mois" tick={{ fontSize: 11, fill: CHART_AXIS }} stroke={CHART_GRID} />
                  <YAxis
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    stroke={CHART_GRID}
                    tickFormatter={(v) => (v >= 1000 ? Math.round(v / 1000) + 'k' : v)}
                  />
                  <Tooltip content={<TooltipDH />} />
                  <Area
                    type="monotone" dataKey="ca" name="CA HT"
                    stroke={CHART_INFO} strokeWidth={2.5}
                    fill="url(#caGradient)" dot={false}
                  />
                </AreaChart>
              </ResponsiveContainer>
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
              <ResponsiveContainer width="100%" height={220}>
                <BarChart
                  data={top_produits}
                  layout="vertical"
                  margin={{ top: 4, right: 20, bottom: 0, left: 0 }}
                >
                  <CartesianGrid strokeDasharray="3 3" stroke={CHART_GRID} horizontal={false} />
                  <XAxis type="number" tick={{ fontSize: 11, fill: CHART_AXIS }} stroke={CHART_GRID} />
                  <YAxis
                    dataKey="nom" type="category"
                    tick={{ fontSize: 11, fill: CHART_AXIS }}
                    stroke={CHART_GRID}
                    width={100}
                  />
                  <Tooltip
                    formatter={(v) => [formatNumber(v) + ' unités', 'Qté vendue']}
                    contentStyle={CHART_TOOLTIP_STYLE}
                  />
                  <Bar dataKey="qte" fill={CHART_PRIMARY} radius={[0, 6, 6, 0]} />
                </BarChart>
              </ResponsiveContainer>
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
            <ConversionBar label="Devis créés" value={conversion.nb_devis} max={conversion.nb_devis} tone="bg-info" />
            <ConversionBar label="Devis acceptés" value={conversion.nb_acceptes} max={conversion.nb_devis} tone="bg-success" />
            <ConversionBar label="Factures émises" value={conversion.nb_factures} max={conversion.nb_devis} tone="bg-primary" />
            {conversion.nb_devis > 0 && (
              <div className="mt-4 rounded-lg bg-muted px-3.5 py-2.5 text-sm text-muted-foreground">
                Taux de conversion global :{' '}
                <strong className="tabular-nums text-foreground">
                  {Math.round((conversion.nb_factures / conversion.nb_devis) * 100)}%
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
            <div className="overflow-x-auto">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Client</th>
                    <th className="ta-right">Nb factures</th>
                    <th className="ta-right">Montant total</th>
                    <th className="ta-right">Retard max</th>
                  </tr>
                </thead>
                <tbody>
                  {creances.map((c, i) => (
                    <tr key={i}>
                      <td className="font-medium">{c.client}</td>
                      <td className="ta-right text-muted-foreground tabular-nums">{formatNumber(c.nb_factures)}</td>
                      <td className="ta-right font-semibold tabular-nums text-destructive">{dh(c.montant_total)}</td>
                      <td className="ta-right">
                        {c.jours_retard_max > 0 ? (
                          <StatusPill tone="danger" dot={false} label={`${c.jours_retard_max} j`} />
                        ) : (
                          <span className="text-muted-foreground">—</span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </CardContent>
        </Card>
      )}
    </div>
  )
}
