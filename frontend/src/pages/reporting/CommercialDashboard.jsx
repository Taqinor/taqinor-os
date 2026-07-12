import { useEffect, useMemo, useState } from 'react'
import { TrendingUp, Award, Target, Clock, AlertCircle, Download } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { formatMAD, formatNumber } from '../../lib/format'
import {
  Card, CardContent, CardTitle, Skeleton, EmptyState, Segmented, Stat, Button, Badge, toast,
  ErrorBoundary,
} from '../../ui'
import { BarArrondie } from '../../ui/charts'
import { Table } from './Table'
import { rowsToCSV, exportFileName } from '../../ui/datatable/csv'

// ── Utilitaires d'affichage ────────────────────────────────────────────────
const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)
const mad = (v) => formatMAD(v, { decimals: 0 })

// Ton de barre d'entonnoir selon le taux de conversion (tokens du kit charts).
const barTone = (pctVal) => {
  if (pctVal >= 60) return 'success'
  if (pctVal >= 30) return 'warning'
  return 'info'
}

const TABS = [
  { value: 'funnel', label: 'Entonnoir & vélocité' },
  { value: 'leaderboard', label: 'Classement' },
  { value: 'winloss', label: 'Gains / Pertes' },
]

export default function CommercialDashboard() {
  const [tab, setTab] = useState('funnel')
  const [dash, setDash] = useState(null)
  const [winLoss, setWinLoss] = useState(null)
  const [loadingDash, setLoadingDash] = useState(true)
  const [loadingWL, setLoadingWL] = useState(true)
  const [errDash, setErrDash] = useState(false)
  const [errWL, setErrWL] = useState(false)

  useEffect(() => {
    reportingApi.commercialDashboard()
      .then(r => { setDash(r.data); setErrDash(false) })
      .catch(() => setErrDash(true))
      .finally(() => setLoadingDash(false))
  }, [])

  useEffect(() => {
    reportingApi.winLossBySource()
      .then(r => { setWinLoss(r.data); setErrWL(false) })
      .catch(() => setErrWL(true))
      .finally(() => setLoadingWL(false))
  }, [])

  // Données d'entonnoir prêtes pour BarArrondie (barres horizontales, ton dérivé).
  const funnelBars = useMemo(
    () => (dash?.funnel || []).map(f => ({
      label: f.label,
      value: f.conversion_pct ?? 0,
      count: f.count,
      color: barTone(f.conversion_pct ?? 0),
    })),
    [dash],
  )

  // VX29 — Export du classement (frontend-only : pas d'endpoint xlsx pour ce
  // tableau de bord ; le kit CSV est ouvert nativement par Excel via le BOM
  // UTF-8, sans dépendance ni changement backend). `prix_achat` jamais exposé.
  const exportLeaderboard = () => {
    const rows = dash?.leaderboard || []
    if (rows.length === 0) {
      toast.error('Aucun commercial à exporter.')
      return
    }
    const columns = [
      { id: 'rang', header: 'Rang', exportValue: (_r, i) => i + 1 },
      { id: 'commercial', header: 'Commercial' },
      { id: 'ca_ht', header: 'CA HT signé' },
      { id: 'nb_devis_signes', header: 'Devis signés' },
      { id: 'avg_deal_ht', header: 'Deal moyen HT' },
      { id: 'win_rate_pct', header: 'Taux victoire (%)' },
      { id: 'kwc', header: 'kWc' },
    ]
    const csv = rowsToCSV(rows.map((r, i) => ({ ...r, rang: i + 1 })), columns)
    const blob = new Blob([csv], { type: 'text/csv;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = exportFileName('classement-commercial', { ext: 'csv' })
    document.body.appendChild(a)
    a.click()
    a.remove()
    setTimeout(() => URL.revokeObjectURL(url), 1000)
    toast.success('Classement exporté.')
  }

  return (
    <div className="ui-root page flex flex-col gap-6">
      {/* En-tête */}
      <div className="page-header">
        <h2 className="font-display text-2xl font-semibold tracking-tight">Tableau commercial</h2>
      </div>

      {/* KPIs rapides */}
      {loadingDash ? (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          {[1, 2, 3, 4].map(i => <Skeleton key={i} className="h-20 rounded-xl" />)}
        </div>
      ) : errDash ? null : dash && (
        <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
          <Stat icon={Target} label="Total leads" value={dash.total_leads} />
          <Stat icon={Award} label="Leads signés" value={dash.total_signes} />
          <Stat icon={TrendingUp} label="Taux de victoire" value={pct(dash.win_rate_pct)} tone="impact" />
          <Stat icon={Clock} label="Vélocité moyenne" value={jours(dash.sales_velocity?.avg_days)} />
        </div>
      )}

      {/* Onglets */}
      <Segmented value={tab} onChange={setTab} options={TABS} />

      {/* ── Onglet Entonnoir ─────────────────────────────────────────────── */}
      {/* VX205 — chaque onglet isolé dans SA PROPRE `ErrorBoundary` : un throw
          n'emporte que ce panneau, le Segmented (hors boundary) reste
          utilisable pour changer d'onglet. */}
      {tab === 'funnel' && (
        <ErrorBoundary>
          {loadingDash && <LoadingRows n={6} />}
          {errDash && <ErrorBanner message="Impossible de charger le tableau de bord." />}
          {!loadingDash && !errDash && dash && (
            <div className="flex flex-col gap-4">
              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-4 text-sm uppercase tracking-wide text-muted-foreground">
                    Entonnoir de conversion
                  </CardTitle>
                  {funnelBars.length === 0 ? (
                    <EmptyState
                      icon={Target}
                      title="Aucune donnée d'entonnoir"
                      description="Aucun lead n'a encore progressé dans le pipeline sur cette période."
                    />
                  ) : (
                    <BarArrondie
                      data={funnelBars}
                      layout="vertical"
                      height={Math.max(160, funnelBars.length * 42)}
                      categoryWidth={130}
                      tooltipFormat={(value, _name, entry) =>
                        `${entry?.payload?.count ?? 0} leads · ${pct(value)}`}
                    />
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-4 text-sm uppercase tracking-wide text-muted-foreground">
                    Temps moyen par étape (goulots d'étranglement)
                  </CardTitle>
                  <Table
                    aria-label="Temps moyen par étape"
                    columns={[
                      { key: 'label', header: 'Étape' },
                      { key: 'avg_days', header: 'Durée moy.', align: 'right', cell: (r) => jours(r.avg_days) },
                      { key: 'sample_count', header: 'Échantillon', align: 'right' },
                    ]}
                    rows={dash.time_in_stage}
                    getRowKey={(r) => r.stage}
                    empty={<EmptyState icon={Clock} title="Aucune mesure" description="Pas encore de transitions d'étape mesurées." />}
                  />
                </CardContent>
              </Card>

              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-2 text-sm uppercase tracking-wide text-muted-foreground">
                    Vélocité de vente
                  </CardTitle>
                  <p className="text-sm text-muted-foreground">
                    Délai moyen lead → devis accepté :
                    <strong className="ml-1.5 text-foreground">{jours(dash.sales_velocity?.avg_days)}</strong>
                    {dash.sales_velocity?.sample_count > 0 && (
                      <span className="ml-2 text-muted-foreground">
                        ({dash.sales_velocity.sample_count} devis)
                      </span>
                    )}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </ErrorBoundary>
      )}

      {/* ── Onglet Classement ─────────────────────────────────────────────── */}
      {tab === 'leaderboard' && (
        <ErrorBoundary>
          {loadingDash && <LoadingRows n={4} />}
          {errDash && <ErrorBanner message="Impossible de charger le classement." />}
          {!loadingDash && !errDash && dash && (
            <Card>
              <CardContent className="pt-4">
                <div className="mb-4 flex items-center justify-between gap-3">
                  <CardTitle className="text-sm uppercase tracking-wide text-muted-foreground">
                    Classement commerciaux
                  </CardTitle>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={exportLeaderboard}
                    disabled={(dash.leaderboard || []).length === 0}
                  >
                    <Download className="size-3.5" />
                    Exporter
                  </Button>
                </div>
                {dash.leaderboard.length === 0 ? (
                  <EmptyState
                    icon={Award}
                    title="Aucun devis signé"
                    description="Aucun devis signé sur cette période."
                  />
                ) : (
                  <Table
                    aria-label="Classement commerciaux"
                    columns={[
                      { key: 'rang', header: '#', cell: (_r, i) => <span className="text-muted-foreground">{i + 1}</span> },
                      { key: 'commercial', header: 'Commercial', cell: (r) => <span className="font-medium">{r.commercial}</span> },
                      { key: 'ca_ht', header: 'CA HT signé', align: 'right', cell: (r) => mad(r.ca_ht) },
                      { key: 'nb_devis_signes', header: 'Devis signés', align: 'right' },
                      { key: 'avg_deal_ht', header: 'Deal moyen HT', align: 'right', cell: (r) => mad(r.avg_deal_ht) },
                      { key: 'win_rate_pct', header: 'Taux victoire', align: 'right', cell: (r) => pct(r.win_rate_pct) },
                      {
                        key: 'kwc',
                        header: 'kWc',
                        align: 'right',
                        cell: (r) => (parseFloat(r.kwc || 0) > 0 ? `${formatNumber(r.kwc, { decimals: 1 })} kWc` : '—'),
                      },
                    ]}
                    rows={dash.leaderboard}
                    getRowKey={(r) => r.commercial}
                  />
                )}
              </CardContent>
            </Card>
          )}
        </ErrorBoundary>
      )}

      {/* ── Onglet Gains / Pertes ─────────────────────────────────────────── */}
      {tab === 'winloss' && (
        <ErrorBoundary>
          {loadingWL && <LoadingRows n={5} />}
          {errWL && <ErrorBanner message="Impossible de charger les données gains/pertes." />}
          {!loadingWL && !errWL && winLoss && (
            <div className="flex flex-col gap-4">
              {/* Récapitulatif */}
              <div className="grid grid-cols-2 gap-4 lg:grid-cols-4">
                <Stat label="Total leads" value={winLoss.summary.nb_total} />
                <Stat label="Gagnés (Signés)" value={winLoss.summary.nb_won} tone="impact" />
                <Stat label="Perdus" value={winLoss.summary.nb_lost} />
                <Stat label="Taux de clôture global" value={pct(winLoss.summary.overall_close_rate_pct)} tone="impact" />
              </div>

              {/* Taux par canal marketing */}
              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-4 text-sm uppercase tracking-wide text-muted-foreground">
                    Taux de clôture par canal
                  </CardTitle>
                  <Table
                    aria-label="Taux de clôture par canal"
                    columns={[
                      { key: 'label', header: 'Canal' },
                      { key: 'total', header: 'Total', align: 'right' },
                      { key: 'won', header: 'Gagnés', align: 'right' },
                      { key: 'close_rate_pct', header: 'Taux', align: 'right', cell: (r) => <span className="font-medium">{pct(r.close_rate_pct)}</span> },
                    ]}
                    rows={winLoss.by_canal}
                    getRowKey={(r) => r.canal}
                    empty={<EmptyState icon={AlertCircle} title="Aucune donnée" description="Pas encore de leads rattachés à un canal." />}
                  />
                </CardContent>
              </Card>

              {/* Top motifs de perte */}
              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-4 text-sm uppercase tracking-wide text-muted-foreground">
                    Top motifs de perte
                  </CardTitle>
                  {winLoss.top_loss_reasons.length === 0 ? (
                    <EmptyState
                      icon={Award}
                      title="Aucune perte"
                      description="Aucun lead perdu sur cette période."
                    />
                  ) : (
                    <div className="flex flex-col gap-2">
                      {winLoss.top_loss_reasons.map((r, i) => (
                        <div key={r.motif} className="flex items-center gap-3">
                          <span className="w-6 text-right text-xs text-muted-foreground">{i + 1}</span>
                          <span className="flex-1 text-sm">{r.motif}</span>
                          <Badge tone="danger">{r.count}</Badge>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Par source technique */}
              <Card>
                <CardContent className="pt-4">
                  <CardTitle className="mb-4 text-sm uppercase tracking-wide text-muted-foreground">
                    Taux par source technique
                  </CardTitle>
                  <Table
                    aria-label="Taux par source technique"
                    columns={[
                      { key: 'label', header: 'Source' },
                      { key: 'total', header: 'Total', align: 'right' },
                      { key: 'won', header: 'Gagnés', align: 'right' },
                      { key: 'close_rate_pct', header: 'Taux', align: 'right', cell: (r) => <span className="font-medium">{pct(r.close_rate_pct)}</span> },
                    ]}
                    rows={winLoss.by_source_technique}
                    getRowKey={(r) => r.source}
                    empty={<EmptyState icon={AlertCircle} title="Aucune donnée" description="Pas encore de source technique renseignée." />}
                  />
                </CardContent>
              </Card>
            </div>
          )}
        </ErrorBoundary>
      )}
    </div>
  )
}

// ── Sous-composants locaux ─────────────────────────────────────────────────

function LoadingRows({ n }) {
  return (
    <div className="flex flex-col gap-3">
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} className="h-10 rounded-md" />
      ))}
    </div>
  )
}

function ErrorBanner({ message }) {
  return (
    <div className="flex items-center gap-2 rounded-lg bg-destructive/12 px-4 py-3.5 text-sm text-destructive">
      <AlertCircle className="size-4" />
      {message}
    </div>
  )
}
