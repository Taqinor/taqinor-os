import { useEffect, useState } from 'react'
import { TrendingUp, Award, Target, Clock, BarChart3, AlertCircle } from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import { formatMAD, formatNumber } from '../../lib/format'
import { Card, CardContent, Skeleton, EmptyState, Segmented } from '../../ui'

// ── Utilitaires d'affichage ────────────────────────────────────────────────
const pct = (v) => (v == null ? '—' : `${v} %`)
const jours = (v) => (v == null ? '—' : `${v} j`)
const mad = (v) => formatMAD(v, { decimals: 0 })

// Couleur de barre d'entonnoir selon le taux de conversion.
const barColor = (pctVal) => {
  if (pctVal >= 60) return 'var(--color-success, #22c55e)'
  if (pctVal >= 30) return 'var(--color-warning, #f59e0b)'
  return 'var(--color-info, #3b82f6)'
}

const TABS = [
  { value: 'funnel',    label: 'Entonnoir & vélocité' },
  { value: 'leaderboard', label: 'Classement' },
  { value: 'winloss',  label: 'Gains / Pertes' },
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

  return (
    <div className="ui-root page">
      {/* En-tête */}
      <div className="page-header" style={{ marginBottom: '1.25rem' }}>
        <h2>Tableau commercial</h2>
      </div>

      {/* KPIs rapides */}
      {loadingDash ? (
        <div style={{ display: 'flex', gap: '1rem', marginBottom: '1.5rem' }}>
          {[1, 2, 3, 4].map(i => <Skeleton key={i} style={{ flex: 1, height: '80px', borderRadius: '8px' }} />)}
        </div>
      ) : errDash ? null : dash && (
        <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap', marginBottom: '1.5rem' }}>
          <KpiCard
            icon={<Target size={20} />}
            label="Total leads"
            value={dash.total_leads}
          />
          <KpiCard
            icon={<Award size={20} />}
            label="Leads signés"
            value={dash.total_signes}
          />
          <KpiCard
            icon={<TrendingUp size={20} />}
            label="Taux de victoire"
            value={pct(dash.win_rate_pct)}
            highlight
          />
          <KpiCard
            icon={<Clock size={20} />}
            label="Vélocité moyenne"
            value={jours(dash.sales_velocity?.avg_days)}
          />
        </div>
      )}

      {/* Onglets */}
      <Segmented
        value={tab}
        onChange={setTab}
        options={TABS}
        style={{ marginBottom: '1.25rem' }}
      />

      {/* ── Onglet Entonnoir ─────────────────────────────────────────────── */}
      {tab === 'funnel' && (
        <>
          {loadingDash && <LoadingRows n={6} />}
          {errDash && <ErrorBanner message="Impossible de charger le tableau de bord." />}
          {!loadingDash && !errDash && dash && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Entonnoir de conversion
                  </h3>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
                    {dash.funnel.map(f => (
                      <div key={f.stage}>
                        <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '0.25rem', fontSize: '0.875rem' }}>
                          <span>{f.label}</span>
                          <span style={{ opacity: 0.65 }}>{f.count} leads · {pct(f.conversion_pct)}</span>
                        </div>
                        <div style={{ height: '6px', background: 'var(--color-muted, #e2e8f0)', borderRadius: '3px', overflow: 'hidden' }}>
                          <div style={{
                            height: '100%',
                            width: `${f.conversion_pct}%`,
                            background: barColor(f.conversion_pct),
                            borderRadius: '3px',
                            transition: 'width 0.4s ease',
                          }} />
                        </div>
                      </div>
                    ))}
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Temps moyen par étape (goulots d'étranglement)
                  </h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', opacity: 0.6, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                        <th style={{ paddingBottom: '0.5rem' }}>Étape</th>
                        <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Durée moy.</th>
                        <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Échantillon</th>
                      </tr>
                    </thead>
                    <tbody>
                      {dash.time_in_stage.map(t => (
                        <tr key={t.stage} style={{ borderTop: '1px solid var(--color-border, #e2e8f0)' }}>
                          <td style={{ padding: '0.5rem 0' }}>{t.label}</td>
                          <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{jours(t.avg_days)}</td>
                          <td style={{ textAlign: 'right', padding: '0.5rem 0', opacity: 0.5 }}>{t.sample_count}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>

              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '0.5rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Vélocité de vente
                  </h3>
                  <p style={{ fontSize: '0.875rem', opacity: 0.8 }}>
                    Délai moyen lead → devis accepté :
                    <strong style={{ marginLeft: '0.4rem' }}>{jours(dash.sales_velocity?.avg_days)}</strong>
                    {dash.sales_velocity?.sample_count > 0 && (
                      <span style={{ opacity: 0.5, marginLeft: '0.5rem' }}>
                        ({dash.sales_velocity.sample_count} devis)
                      </span>
                    )}
                  </p>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}

      {/* ── Onglet Classement ─────────────────────────────────────────────── */}
      {tab === 'leaderboard' && (
        <>
          {loadingDash && <LoadingRows n={4} />}
          {errDash && <ErrorBanner message="Impossible de charger le classement." />}
          {!loadingDash && !errDash && dash && (
            <Card>
              <CardContent style={{ paddingTop: '1rem' }}>
                <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                  Classement commerciaux
                </h3>
                {dash.leaderboard.length === 0 ? (
                  <EmptyState message="Aucun devis signé sur cette période." />
                ) : (
                  <div style={{ overflowX: 'auto' }}>
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                      <thead>
                        <tr style={{ textAlign: 'left', opacity: 0.6, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                          <th style={{ paddingBottom: '0.5rem' }}>#</th>
                          <th style={{ paddingBottom: '0.5rem' }}>Commercial</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>CA HT signé</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Devis signés</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Deal moyen HT</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Taux victoire</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>kWc</th>
                        </tr>
                      </thead>
                      <tbody>
                        {dash.leaderboard.map((r, i) => (
                          <tr key={r.commercial} style={{ borderTop: '1px solid var(--color-border, #e2e8f0)' }}>
                            <td style={{ padding: '0.5rem 0', opacity: 0.5 }}>{i + 1}</td>
                            <td style={{ padding: '0.5rem 0.5rem 0.5rem 0', fontWeight: 500 }}>{r.commercial}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{mad(r.ca_ht)}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{r.nb_devis_signes}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{mad(r.avg_deal_ht)}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{pct(r.win_rate_pct)}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0', opacity: 0.7 }}>
                              {parseFloat(r.kwc || 0) > 0 ? `${formatNumber(r.kwc, { decimals: 1 })} kWc` : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                )}
              </CardContent>
            </Card>
          )}
        </>
      )}

      {/* ── Onglet Gains / Pertes ─────────────────────────────────────────── */}
      {tab === 'winloss' && (
        <>
          {loadingWL && <LoadingRows n={5} />}
          {errWL && <ErrorBanner message="Impossible de charger les données gains/pertes." />}
          {!loadingWL && !errWL && winLoss && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '1rem' }}>
              {/* Récapitulatif */}
              <div style={{ display: 'flex', gap: '1rem', flexWrap: 'wrap' }}>
                <KpiCard label="Total leads" value={winLoss.summary.nb_total} />
                <KpiCard label="Gagnés (Signés)" value={winLoss.summary.nb_won} highlight />
                <KpiCard label="Perdus" value={winLoss.summary.nb_lost} />
                <KpiCard label="Taux de clôture global" value={pct(winLoss.summary.overall_close_rate_pct)} highlight />
              </div>

              {/* Taux par canal marketing */}
              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Taux de clôture par canal
                  </h3>
                  {winLoss.by_canal.length === 0 ? (
                    <EmptyState message="Aucune donnée." />
                  ) : (
                    <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                      <thead>
                        <tr style={{ textAlign: 'left', opacity: 0.6, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                          <th style={{ paddingBottom: '0.5rem' }}>Canal</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Total</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Gagnés</th>
                          <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Taux</th>
                        </tr>
                      </thead>
                      <tbody>
                        {winLoss.by_canal.map(r => (
                          <tr key={r.canal} style={{ borderTop: '1px solid var(--color-border, #e2e8f0)' }}>
                            <td style={{ padding: '0.5rem 0' }}>{r.label}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{r.total}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{r.won}</td>
                            <td style={{ textAlign: 'right', padding: '0.5rem 0', fontWeight: 500 }}>{pct(r.close_rate_pct)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                </CardContent>
              </Card>

              {/* Top motifs de perte */}
              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Top motifs de perte
                  </h3>
                  {winLoss.top_loss_reasons.length === 0 ? (
                    <EmptyState message="Aucun lead perdu sur cette période." />
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.5rem' }}>
                      {winLoss.top_loss_reasons.map((r, i) => (
                        <div key={r.motif} style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
                          <span style={{ opacity: 0.4, width: '1.5rem', textAlign: 'right', fontSize: '0.75rem' }}>{i + 1}</span>
                          <span style={{ flex: 1, fontSize: '0.875rem' }}>{r.motif}</span>
                          <span style={{ fontSize: '0.875rem', fontWeight: 600 }}>{r.count}</span>
                        </div>
                      ))}
                    </div>
                  )}
                </CardContent>
              </Card>

              {/* Par source technique */}
              <Card>
                <CardContent style={{ paddingTop: '1rem' }}>
                  <h3 style={{ marginBottom: '1rem', fontSize: '0.875rem', fontWeight: 600, opacity: 0.7, textTransform: 'uppercase', letterSpacing: '0.05em' }}>
                    Taux par source technique
                  </h3>
                  <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: '0.875rem' }}>
                    <thead>
                      <tr style={{ textAlign: 'left', opacity: 0.6, fontSize: '0.75rem', textTransform: 'uppercase' }}>
                        <th style={{ paddingBottom: '0.5rem' }}>Source</th>
                        <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Total</th>
                        <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Gagnés</th>
                        <th style={{ paddingBottom: '0.5rem', textAlign: 'right' }}>Taux</th>
                      </tr>
                    </thead>
                    <tbody>
                      {winLoss.by_source_technique.map(r => (
                        <tr key={r.source} style={{ borderTop: '1px solid var(--color-border, #e2e8f0)' }}>
                          <td style={{ padding: '0.5rem 0' }}>{r.label}</td>
                          <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{r.total}</td>
                          <td style={{ textAlign: 'right', padding: '0.5rem 0' }}>{r.won}</td>
                          <td style={{ textAlign: 'right', padding: '0.5rem 0', fontWeight: 500 }}>{pct(r.close_rate_pct)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </CardContent>
              </Card>
            </div>
          )}
        </>
      )}
    </div>
  )
}

// ── Sous-composants locaux ─────────────────────────────────────────────────

function KpiCard({ icon, label, value, highlight }) {
  return (
    <div style={{
      flex: '1 1 160px',
      background: 'var(--color-surface, #fff)',
      border: '1px solid var(--color-border, #e2e8f0)',
      borderRadius: '8px',
      padding: '1rem',
      display: 'flex',
      flexDirection: 'column',
      gap: '0.25rem',
    }}>
      {icon && <span style={{ opacity: 0.5, marginBottom: '0.25rem' }}>{icon}</span>}
      <span style={{ fontSize: '0.75rem', opacity: 0.6, textTransform: 'uppercase', letterSpacing: '0.05em' }}>{label}</span>
      <span style={{
        fontSize: '1.375rem',
        fontWeight: 700,
        color: highlight ? 'var(--color-primary, #4a56d4)' : 'inherit',
      }}>{value}</span>
    </div>
  )
}

function LoadingRows({ n }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '0.75rem' }}>
      {Array.from({ length: n }).map((_, i) => (
        <Skeleton key={i} style={{ height: '40px', borderRadius: '6px' }} />
      ))}
    </div>
  )
}

function ErrorBanner({ message }) {
  return (
    <div style={{
      display: 'flex', alignItems: 'center', gap: '0.5rem',
      padding: '0.875rem 1rem', borderRadius: '8px',
      background: 'var(--color-error-bg, #fee2e2)',
      color: 'var(--color-error, #ef4444)',
      fontSize: '0.875rem',
    }}>
      <AlertCircle size={16} />
      {message}
    </div>
  )
}
