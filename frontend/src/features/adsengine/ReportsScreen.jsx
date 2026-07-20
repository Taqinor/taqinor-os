import { useEffect, useState, useMemo, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { BarChart3, Download, ClipboardList, Printer, Scale } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeVariants, normalizeFunnel, normalizeCohorts, normalizeLeaderboard,
  normalizeScatter, hasRetentionData, formatMAD, formatNumber, formatPercent,
} from './adsengine'
import DataWindowNotice from './DataWindowNotice'
import AlertCenter from './AlertCenter'
import CommandPalette from './CommandPalette'
import MetricHelp from './MetricHelp'

/* ============================================================================
   ENG45 — Drill-downs reporting (consomme ENG33).
   ----------------------------------------------------------------------------
   Trois vues d'analyse fine + un export CSV :
   - TABLE des variantes (impressions, réponses WhatsApp, coût, coût/réponse) ;
   - ENTONNOIR de campagne (étapes ordonnées avec leur valeur) ;
   - COHORTES avec le lag médian jusqu'à la signature.
   L'export CSV est SERVI PAR LE BACKEND (ReportExportView, PUB12) : source de
   vérité unique incluant la table de réconciliation — jamais un CSV fabriqué
   côté client (qui divergerait du serveur).

   ADSDEEP47 — un second ONGLET « Créatifs » : classement spend-weighted par
   hook/angle/format + nuage hook rate × dépense (quadrants FR « pépites
   cachées »/« gouffres »/« gagnants confirmés »/« à surveiller »), période
   sélectionnable (7/30/90 jours).
   ========================================================================== */

const DIMENSIONS = [
  { key: 'hook', label: 'Accroche' },
  { key: 'angle', label: 'Angle' },
  { key: 'format', label: 'Format' },
]

const PERIODS = [
  { key: 7, label: '7 jours' },
  { key: 30, label: '30 jours' },
  { key: 90, label: '90 jours' },
]

// ADSDEEP63 — libellés FR des sections de l'audit de compte à la demande.
const AUDIT_SECTION_LABELS = {
  naming: 'Structure & nommage',
  fragmentation_budgetaire: 'Fragmentation budgétaire',
  fatigue: 'Fatigue créative',
  tracking: 'Tracking (pixel/CAPI/UTM)',
  fenetres_donnees: 'Fenêtres de données',
}
const AUDIT_SECTION_ORDER = [
  'naming', 'fragmentation_budgetaire', 'fatigue', 'tracking', 'fenetres_donnees',
]
const AUDIT_STATUT_STYLE = {
  ok: { bg: '#dcfce7', color: '#166534', label: 'OK' },
  attention: { bg: '#fef3c7', color: '#92400e', label: 'Attention' },
  inconnu: { bg: '#f1f5f9', color: '#475569', label: 'Non calculable' },
  info: { bg: '#eff6ff', color: '#1e40af', label: 'Info' },
}

function periodParams(days) {
  const fin = new Date()
  const debut = new Date(fin)
  debut.setDate(debut.getDate() - (days - 1))
  const iso = (d) => d.toISOString().slice(0, 10)
  return { debut: iso(debut), fin: iso(fin) }
}

// DATAPUB3 — graphe SVG fait-main (aucune lib de charts, idiome du module) :
// barres = leads Odoo (clair = total, foncé = attribués), courbe = dépense.
function LeadsTimeseriesChart({ points }) {
  if (!points || points.length === 0) return null
  const maxLeads = Math.max(...points.map(p => p.leads_total || 0), 1)
  const maxSpend = Math.max(...points.map(p => Number(p.spend) || 0), 1)
  const barW = 26
  const gap = 10
  const h = 160
  const w = points.length * (barW + gap) + gap
  const xAt = (i) => gap + i * (barW + gap)
  const spendLine = points.map((p, i) => {
    const cx = xAt(i) + barW / 2
    const cy = h - ((Number(p.spend) || 0) / maxSpend) * h
    return `${cx},${Number.isFinite(cy) ? cy : h}`
  }).join(' ')
  return (
    <svg data-testid="ae-leads-chart" role="img"
      aria-label="Leads Odoo dans le temps (barres) et dépense (courbe)"
      viewBox={`0 0 ${w} ${h}`} width="100%" height={h}
      preserveAspectRatio="none" style={{ display: 'block' }}>
      {points.map((p, i) => {
        const totalH = ((p.leads_total || 0) / maxLeads) * h
        const attrH = ((p.leads_attributed || 0) / maxLeads) * h
        return (
          <g key={p.period}>
            <rect x={xAt(i)} y={h - totalH} width={barW} height={totalH}
              fill="#bfdbfe" data-testid="ae-leads-bar-total" />
            <rect x={xAt(i)} y={h - attrH} width={barW} height={attrH}
              fill="#2563eb" data-testid="ae-leads-bar-attributed" />
          </g>
        )
      })}
      <polyline points={spendLine} fill="none" stroke="#f59e0b" strokeWidth="2" />
    </svg>
  )
}

export default function ReportsScreen() {
  const [tab, setTab] = useState('apercu')
  const [variants, setVariants] = useState([])
  const [funnel, setFunnel] = useState([])
  const [cohorts, setCohorts] = useState([])
  const [loading, setLoading] = useState(true)

  const [dimension, setDimension] = useState('hook')
  const [periodDays, setPeriodDays] = useState(30)
  const [leaderboard, setLeaderboard] = useState({ classement: [], untaggedCount: 0 })
  const [scatter, setScatter] = useState({ points: [], medianHookRate: null, medianSpend: null })
  const [creativeLoading, setCreativeLoading] = useState(true)

  // ADSDEEP63 — audit de compte à la demande : jamais auto-chargé au montage,
  // seulement au clic sur « Lancer l'audit ».
  const [auditData, setAuditData] = useState(null)
  const [auditLoading, setAuditLoading] = useState(false)
  const [auditError, setAuditError] = useState(false)

  const runAudit = useCallback(() => {
    setAuditLoading(true)
    setAuditError(false)
    adsengineApi.reports.audit()
      .then(r => setAuditData(r.data))
      .catch(() => setAuditError(true))
      .finally(() => setAuditLoading(false))
  }, [])

  // DATAPUB2 — bilan d'attribution des leads Odoo (chargé à l'ouverture de
  // l'onglet, jamais au montage : évite un appel Odoo inutile sur les autres
  // onglets).
  const [bilan, setBilan] = useState(null)
  const [bilanLoading, setBilanLoading] = useState(false)

  const loadBilan = useCallback(() => {
    setBilanLoading(true)
    adsengineApi.reports.attributionBilan()
      .then(r => setBilan(r.data))
      .catch(() => setBilan(null))
      .finally(() => setBilanLoading(false))
  }, [])

  // DATAPUB3 — série temporelle des leads Odoo (jour/semaine).
  const [leadsSeries, setLeadsSeries] = useState(null)
  const [leadsGran, setLeadsGran] = useState('jour')
  const [leadsLoading, setLeadsLoading] = useState(false)

  const loadLeads = useCallback(() => {
    setLeadsLoading(true)
    adsengineApi.reports.leadsTimeseries({ granularite: leadsGran })
      .then(r => setLeadsSeries(r.data))
      .catch(() => setLeadsSeries(null))
      .finally(() => setLeadsLoading(false))
  }, [leadsGran])

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.reports.variants()
      .then(r => setVariants(normalizeVariants(r.data)))
      .catch(() => setVariants([]))
    adsengineApi.reports.funnel()
      .then(r => setFunnel(normalizeFunnel(r.data)))
      .catch(() => setFunnel([]))
    adsengineApi.reports.cohorts()
      .then(r => setCohorts(normalizeCohorts(r.data)))
      .catch(() => setCohorts([]))
      .finally(() => setLoading(false))
  }, [])

  const loadCreative = useCallback(() => {
    setCreativeLoading(true)
    const params = { dimension, ...periodParams(periodDays) }
    adsengineApi.reports.leaderboard(params)
      .then(r => setLeaderboard(normalizeLeaderboard(r.data)))
      .catch(() => setLeaderboard({ classement: [], untaggedCount: 0 }))
    adsengineApi.reports.scatter(periodParams(periodDays))
      .then(r => setScatter(normalizeScatter(r.data)))
      .catch(() => setScatter({ points: [], medianHookRate: null, medianSpend: null }))
      .finally(() => setCreativeLoading(false))
  }, [dimension, periodDays])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])
  // eslint-disable-next-line react-hooks/set-state-in-effect -- rechargement au changement de dimension/période
  useEffect(() => { loadCreative() }, [loadCreative])
  // DATAPUB2 — charge le bilan la première fois que l'onglet est ouvert.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'onglet
  useEffect(() => { if (tab === 'attribution' && bilan === null) loadBilan() }, [tab, bilan, loadBilan])
  // DATAPUB3 — (re)charge la série leads à l'ouverture de l'onglet et au
  // changement de granularité.
  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement à l'ouverture de l'onglet
  useEffect(() => { if (tab === 'leads') loadLeads() }, [tab, loadLeads])

  // Export CSV : SERVI PAR LE BACKEND (PUB12). On télécharge le blob authentifié
  // du ReportExportView (source de vérité unique, table de réconciliation
  // incluse) puis on déclenche l'enregistrement — jamais un CSV fabriqué ici.
  const handleExportCsv = useCallback(() => {
    adsengineApi.reports.export({ table: 'variantes' })
      .then(r => {
        const blob = r.data instanceof Blob
          ? r.data : new Blob([r.data], { type: 'text/csv;charset=utf-8' })
        const url = URL.createObjectURL(blob)
        const a = document.createElement('a')
        a.href = url
        a.download = 'variantes-taqinor.csv'
        document.body.appendChild(a)
        a.click()
        a.remove()
        URL.revokeObjectURL(url)
      })
      .catch(() => {})
  }, [])

  const funnelMax = useMemo(
    () => funnel.reduce((m, e) => Math.max(m, Number.isFinite(e.valeur) ? e.valeur : 0), 0) || 1,
    [funnel])

  return (
    <div className="page ae-reports ae-print-area">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', marginRight: 'auto' }}>
          <BarChart3 size={20} aria-hidden="true" /> Reporting
        </h2>
        {tab === 'apercu' && variants.length > 0 && (
          <button type="button" className="btn btn-primary" data-testid="ae-reports-export"
            onClick={handleExportCsv}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <Download size={15} aria-hidden="true" /> Exporter en CSV
          </button>
        )}
        {/* PUB52 — comparateur côte-à-côte (ads/campagnes) */}
        <Link to="/publicite/comparateur" className="btn btn-light" data-testid="ae-reports-compare-link"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Scale size={15} aria-hidden="true" /> Comparateur
        </Link>
        {/* PUB47 — impression navigateur (feuille globale print.css, VX80) :
            PDF imprimable propre (A4), zéro dépendance nouvelle. Distinct des
            PDF WeasyPrint client (règle #4). */}
        <button type="button" className="btn btn-light" data-testid="ae-reports-print"
          onClick={() => window.print()}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Printer size={15} aria-hidden="true" /> Imprimer / PDF
        </button>
        {/* PUB48 — centre de notifications persistant de la console */}
        <AlertCenter />
        {/* PUB51 — palette de commandes (Ctrl-K) */}
        <CommandPalette />
      </div>

      <div role="tablist" aria-label="Sections du reporting"
        style={{ display: 'flex', gap: '0.5rem', margin: '0 0 1rem' }}>
        <button type="button" role="tab" aria-selected={tab === 'apercu'}
          data-testid="ae-reports-tab-apercu"
          className={`btn ${tab === 'apercu' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('apercu')}>Vue d&apos;ensemble</button>
        <button type="button" role="tab" aria-selected={tab === 'creatifs'}
          data-testid="ae-reports-tab-creatifs"
          className={`btn ${tab === 'creatifs' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('creatifs')}>Créatifs</button>
        <button type="button" role="tab" aria-selected={tab === 'attribution'}
          data-testid="ae-reports-tab-attribution"
          className={`btn ${tab === 'attribution' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('attribution')}>Attribution</button>
        <button type="button" role="tab" aria-selected={tab === 'leads'}
          data-testid="ae-reports-tab-leads"
          className={`btn ${tab === 'leads' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('leads')}>Leads dans le temps</button>
        <button type="button" role="tab" aria-selected={tab === 'audit'}
          data-testid="ae-reports-tab-audit"
          className={`btn ${tab === 'audit' ? 'btn-primary' : 'btn-secondary'}`}
          onClick={() => setTab('audit')}>Audit de compte</button>
      </div>

      {tab === 'apercu' && (
        loading ? <p className="page-loading">Chargement…</p> : (
          <div style={{ display: 'grid', gap: '1.25rem' }}>
            {/* ADSDEEP66 — variantes/entonnoir/cohortes dérivent des insights
                Meta, disponibles 37 mois glissants seulement. */}
            <DataWindowNotice kind="insights" />
            {/* Table des variantes */}
            <section className="ae-reports-variants" data-testid="ae-reports-variants">
              <h3 style={{ margin: '0 0 0.6rem' }}>Variantes</h3>
              {variants.length === 0
                ? <p data-testid="ae-reports-variants-empty" style={{ color: '#64748b' }}>
                    Aucune variante.</p>
                : (
                  <table className="data-table" data-testid="ae-reports-variants-table">
                    <thead>
                      <tr>
                        <th>Variante</th><th>Impressions</th><th>Réponses WhatsApp</th>
                        <th>Coût</th><th>Coût / réponse</th>
                      </tr>
                    </thead>
                    <tbody>
                      {variants.map(v => (
                        <tr key={v.id} data-testid="ae-reports-variant-row">
                          <td data-label="Variante">{v.nom}</td>
                          <td data-label="Impressions">{formatNumber(v.impressions)}</td>
                          <td data-label="Réponses WhatsApp">{formatNumber(v.reponses_whatsapp)}</td>
                          <td data-label="Coût">{formatMAD(v.cout_mad)}</td>
                          <td data-label="Coût / réponse">{formatMAD(v.cout_par_reponse)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </section>

            {/* Entonnoir campagne */}
            <section className="ae-reports-funnel" data-testid="ae-reports-funnel">
              <h3 style={{ margin: '0 0 0.6rem' }}>Entonnoir de campagne</h3>
              {funnel.length === 0
                ? <p data-testid="ae-reports-funnel-empty" style={{ color: '#64748b' }}>
                    Aucune donnée d&apos;entonnoir.</p>
                : (
                  <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
                    {funnel.map(e => (
                      <li key={e.key} data-testid="ae-reports-funnel-step">
                        <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.9rem' }}>
                          <span>{e.label}</span>
                          <strong>{formatNumber(e.valeur)}</strong>
                        </div>
                        <div aria-hidden="true" style={{ height: 10, background: '#f1f5f9',
                          borderRadius: 999, marginTop: '0.25rem', overflow: 'hidden' }}>
                          <div style={{ height: '100%', background: '#2563eb',
                            width: `${((Number.isFinite(e.valeur) ? e.valeur : 0) / funnelMax) * 100}%` }} />
                        </div>
                      </li>
                    ))}
                  </ul>
                )}
            </section>

            {/* Cohortes / lag */}
            <section className="ae-reports-cohorts" data-testid="ae-reports-cohorts">
              <h3 style={{ margin: '0 0 0.6rem' }}>Cohortes &amp; lag jusqu&apos;à la signature</h3>
              {cohorts.length === 0
                ? <p data-testid="ae-reports-cohorts-empty" style={{ color: '#64748b' }}>
                    Aucune cohorte.</p>
                : (
                  <table className="data-table" data-testid="ae-reports-cohorts-table">
                    <thead>
                      <tr><th>Cohorte</th><th>Taille</th><th>Lag médian (jours)</th><th>Signatures</th></tr>
                    </thead>
                    <tbody>
                      {cohorts.map(c => (
                        <tr key={c.id} data-testid="ae-reports-cohort-row">
                          <td data-label="Cohorte">{c.cohorte}</td>
                          <td data-label="Taille">{formatNumber(c.taille)}</td>
                          <td data-label="Lag médian (jours)">{formatNumber(c.lag_jours_median)}</td>
                          <td data-label="Signatures">{formatNumber(c.signatures)}</td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                )}
            </section>
          </div>
        )
      )}

      {tab === 'creatifs' && (
        <div style={{ display: 'grid', gap: '1.25rem' }} data-testid="ae-reports-creatifs">
          <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
            <div role="group" aria-label="Dimension du classement" style={{ display: 'flex', gap: '0.4rem' }}>
              {DIMENSIONS.map(d => (
                <button key={d.key} type="button"
                  data-testid={`ae-creatifs-dimension-${d.key}`}
                  aria-pressed={dimension === d.key}
                  className={`btn ${dimension === d.key ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setDimension(d.key)}>{d.label}</button>
              ))}
            </div>
            <div role="group" aria-label="Période" style={{ display: 'flex', gap: '0.4rem' }}>
              {PERIODS.map(p => (
                <button key={p.key} type="button"
                  data-testid={`ae-creatifs-period-${p.key}`}
                  aria-pressed={periodDays === p.key}
                  className={`btn ${periodDays === p.key ? 'btn-primary' : 'btn-secondary'}`}
                  onClick={() => setPeriodDays(p.key)}>{p.label}</button>
              ))}
            </div>
          </div>

          {creativeLoading ? <p className="page-loading">Chargement…</p> : (
            <>
              {/* Leaderboard spend-weighted */}
              <section className="ae-creatifs-leaderboard" data-testid="ae-creatifs-leaderboard">
                <h3 style={{ margin: '0 0 0.6rem' }}>
                  Classement par {DIMENSIONS.find(d => d.key === dimension)?.label.toLowerCase()}
                </h3>
                {leaderboard.classement.length === 0
                  ? <p data-testid="ae-creatifs-leaderboard-empty" style={{ color: '#64748b' }}>
                      Aucun créatif tagué pour cette dimension.</p>
                  : (
                    <table className="data-table" data-testid="ae-creatifs-leaderboard-table">
                      <thead>
                        <tr>
                          <th>Tag</th><th>Dépense</th><th>Résultats</th>
                          <th>Coût / résultat<MetricHelp metric="cost_per_result" label="Coût / résultat" /></th>
                          <th>Hook rate (pondéré)<MetricHelp metric="hook_rate" label="Hook rate" /></th>
                          <th>Ads</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboard.classement.map(row => (
                          <tr key={row.id} data-testid="ae-creatifs-leaderboard-row">
                            <td data-label="Tag">{row.tag}</td>
                            <td data-label="Dépense">{formatMAD(row.spend)}</td>
                            <td data-label="Résultats">{formatNumber(row.results)}</td>
                            <td data-label="Coût / résultat">{formatMAD(row.costPerResult)}</td>
                            <td data-label="Hook rate (pondéré)">{formatPercent(row.hookRateWeighted, 1)}</td>
                            <td data-label="Ads">{formatNumber(row.adCount)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
                {leaderboard.untaggedCount > 0 && (
                  <p data-testid="ae-creatifs-untagged" style={{ color: '#64748b', fontSize: '0.85rem' }}>
                    {leaderboard.untaggedCount} ad(s) sans tag {dimension} — non classé(s).
                  </p>
                )}
              </section>

              {/* Nuage hook rate × dépense */}
              <section className="ae-creatifs-scatter" data-testid="ae-creatifs-scatter">
                <h3 style={{ margin: '0 0 0.6rem' }}>Nuage hook rate × dépense</h3>
                {scatter.points.length === 0
                  ? <p data-testid="ae-creatifs-scatter-empty" style={{ color: '#64748b' }}>
                      Pas assez de données vidéo pour classer les ads.</p>
                  : (
                    <table className="data-table" data-testid="ae-creatifs-scatter-table">
                      <thead>
                        <tr><th>Ad</th><th>Dépense</th>
                          <th>Hook rate<MetricHelp metric="hook_rate" label="Hook rate" /></th>
                          <th>Quadrant</th>
                          {/* PUB8 — courbe de rétention par ad vidéo (25/50/75/100 %
                              des lectures qui atteignent chaque quartile). */}
                          <th>Rétention (25/50/75/100 %)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {scatter.points.map(p => (
                          <tr key={p.id} data-testid="ae-creatifs-scatter-row">
                            <td data-label="Ad">{p.nom}</td>
                            <td data-label="Dépense">{formatMAD(p.spend)}</td>
                            <td data-label="Hook rate">{formatPercent(p.hookRate, 1)}</td>
                            <td data-label="Quadrant" data-testid="ae-creatifs-scatter-quadrant">{p.quadrantLabel}</td>
                            <td data-label="Rétention (25/50/75/100 %)" data-testid="ae-creatifs-scatter-retention">
                              {hasRetentionData(p)
                                ? [p.retention.p25, p.retention.p50, p.retention.p75, p.retention.p100]
                                    .map(v => formatPercent(v, 0)).join(' · ')
                                : '—'}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
              </section>
            </>
          )}
        </div>
      )}

      {tab === 'attribution' && (
        <div style={{ display: 'grid', gap: '1.25rem' }} data-testid="ae-attribution">
          {bilanLoading && <p className="page-loading">Chargement…</p>}
          {!bilanLoading && !bilan && (
            <p data-testid="ae-attribution-empty" style={{ color: '#64748b' }}>
              Bilan d&apos;attribution indisponible.
            </p>
          )}
          {!bilanLoading && bilan && !bilan.configured && (
            <p data-testid="ae-attribution-unconfigured" style={{ color: '#64748b' }}>
              Odoo n&apos;est pas connecté : aucun lead à attribuer pour l&apos;instant.
            </p>
          )}
          {!bilanLoading && bilan && bilan.odoo_error && (
            <p data-testid="ae-attribution-error" style={{ color: '#b91c1c' }}>
              Lecture Odoo en échec : {bilan.odoo_error}
            </p>
          )}
          {!bilanLoading && bilan && (
            <>
              {/* Bandeau : tous les leads Odoo, jamais ignorés en silence. */}
              <div style={{ display: 'flex', gap: '1.5rem', flexWrap: 'wrap' }}>
                <div data-testid="ae-attribution-total">
                  <div style={{ fontSize: '1.6rem', fontWeight: 700 }}>
                    {formatNumber(bilan.total)}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Leads Odoo</div>
                </div>
                <div data-testid="ae-attribution-attributed">
                  <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#166534' }}>
                    {formatNumber(bilan.attributed)}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Attribués</div>
                </div>
                <div data-testid="ae-attribution-unattributed">
                  <div style={{ fontSize: '1.6rem', fontWeight: 700, color: '#92400e' }}>
                    {formatNumber(bilan.unattributed)}
                  </div>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Non attribués</div>
                </div>
              </div>

              {/* Répartition par palier. */}
              <section data-testid="ae-attribution-tiers">
                <h3 style={{ margin: '0 0 0.6rem' }}>Attribution par palier</h3>
                <table className="data-table" data-testid="ae-attribution-tiers-table">
                  <thead>
                    <tr><th>Palier</th><th>Leads</th></tr>
                  </thead>
                  <tbody>
                    {bilan.tiers.map(t => (
                      <tr key={t.key} data-testid="ae-attribution-tier-row">
                        <td data-label="Palier">{t.label}</td>
                        <td data-label="Leads">{formatNumber(t.count)}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </section>

              {/* Non attribués PAR nom de source (le fondateur voit où ça coince). */}
              <section data-testid="ae-attribution-unattributed-sources">
                <h3 style={{ margin: '0 0 0.6rem' }}>
                  Non attribués par source
                </h3>
                {bilan.unattributed_by_source.length === 0
                  ? <p data-testid="ae-attribution-sources-empty" style={{ color: '#64748b' }}>
                      Aucun lead non attribué.</p>
                  : (
                    <table className="data-table" data-testid="ae-attribution-sources-table">
                      <thead>
                        <tr><th>Nom de source</th><th>Leads</th></tr>
                      </thead>
                      <tbody>
                        {bilan.unattributed_by_source.map((s, i) => (
                          <tr key={i} data-testid="ae-attribution-source-row">
                            <td data-label="Nom de source">{s.source_name || '(vide)'}</td>
                            <td data-label="Leads">{formatNumber(s.count)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
              </section>
            </>
          )}
        </div>
      )}

      {tab === 'leads' && (
        <div style={{ display: 'grid', gap: '1rem' }} data-testid="ae-leads">
          <div role="group" aria-label="Granularité" style={{ display: 'flex', gap: '0.4rem' }}>
            {[{ key: 'jour', label: 'Par jour' }, { key: 'semaine', label: 'Par semaine' }].map(g => (
              <button key={g.key} type="button"
                data-testid={`ae-leads-gran-${g.key}`}
                aria-pressed={leadsGran === g.key}
                className={`btn ${leadsGran === g.key ? 'btn-primary' : 'btn-secondary'}`}
                onClick={() => setLeadsGran(g.key)}>{g.label}</button>
            ))}
          </div>

          {leadsLoading && <p className="page-loading">Chargement…</p>}
          {!leadsLoading && leadsSeries && !leadsSeries.configured && (
            <p data-testid="ae-leads-unconfigured" style={{ color: '#64748b' }}>
              Odoo n&apos;est pas connecté : aucun lead à afficher.
            </p>
          )}
          {!leadsLoading && leadsSeries && (leadsSeries.points || []).length === 0
            && leadsSeries.configured && (
            <p data-testid="ae-leads-empty" style={{ color: '#64748b' }}>
              Aucun lead sur la période.
            </p>
          )}
          {!leadsLoading && leadsSeries && (leadsSeries.points || []).length > 0 && (
            <>
              <div style={{ display: 'flex', gap: '1.25rem', fontSize: '0.8rem', color: '#475569' }}>
                <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#bfdbfe', marginRight: 4 }} />Leads (total)</span>
                <span><span style={{ display: 'inline-block', width: 10, height: 10, background: '#2563eb', marginRight: 4 }} />Attribués</span>
                <span><span style={{ display: 'inline-block', width: 10, height: 2, background: '#f59e0b', marginRight: 4, verticalAlign: 'middle' }} />Dépense</span>
              </div>
              <LeadsTimeseriesChart points={leadsSeries.points} />
              <table className="data-table" data-testid="ae-leads-table">
                <thead>
                  <tr><th>Période</th><th>Leads</th><th>Attribués</th><th>Dépense</th></tr>
                </thead>
                <tbody>
                  {leadsSeries.points.map(p => (
                    <tr key={p.period} data-testid="ae-leads-row">
                      <td data-label="Période">{p.period}</td>
                      <td data-label="Leads">{formatNumber(p.leads_total)}</td>
                      <td data-label="Attribués">{formatNumber(p.leads_attributed)}</td>
                      <td data-label="Dépense">{formatMAD(p.spend)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </>
          )}
        </div>
      )}

      {tab === 'audit' && (
        <div style={{ display: 'grid', gap: '1rem' }} data-testid="ae-audit">
          <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem' }}>
            <button type="button" className="btn btn-primary"
              data-testid="ae-audit-lancer" disabled={auditLoading}
              onClick={runAudit}
              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
              <ClipboardList size={15} aria-hidden="true" />
              {auditLoading ? 'Audit en cours…' : "Lancer l'audit"}
            </button>
            {auditData && (
              <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
                Généré le {auditData.genere_le}
              </span>
            )}
          </div>

          {auditError && (
            <p data-testid="ae-audit-error" style={{ color: '#b91c1c' }}>
              L&apos;audit n&apos;a pas pu être généré. Réessayez.
            </p>
          )}

          {!auditData && !auditLoading && !auditError && (
            <p data-testid="ae-audit-empty" style={{ color: '#64748b' }}>
              Audit à la demande — cliquez sur « Lancer l&apos;audit » pour
              analyser structure/nommage, fragmentation budgétaire, fatigue
              créative, tracking et fenêtres de données.
            </p>
          )}

          {auditData && (
            <div style={{ display: 'grid', gap: '0.9rem' }}>
              {AUDIT_SECTION_ORDER
                .filter(key => auditData.sections?.[key])
                .map(key => {
                  const section = auditData.sections[key]
                  const style = AUDIT_STATUT_STYLE[section.statut] || AUDIT_STATUT_STYLE.inconnu
                  return (
                    <section key={key} data-testid={`ae-audit-section-${key}`}
                      style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.9rem' }}>
                      <div style={{ display: 'flex', justifyContent: 'space-between',
                        alignItems: 'center', marginBottom: '0.4rem' }}>
                        <h3 style={{ margin: 0, fontSize: '1rem' }}>
                          {AUDIT_SECTION_LABELS[key] || key}
                        </h3>
                        <span data-testid={`ae-audit-statut-${key}`}
                          style={{ background: style.bg, color: style.color,
                            borderRadius: 999, padding: '0.15rem 0.6rem', fontSize: '0.75rem' }}>
                          {style.label}
                        </span>
                      </div>
                      <p style={{ margin: '0 0 0.4rem', color: '#334155' }}>{section.resume}</p>
                      {section.items.length > 0 && (
                        <ul style={{ margin: '0 0 0.4rem', paddingLeft: '1.1rem' }}>
                          {section.items.map((item, i) => (
                            <li key={i} data-testid="ae-audit-item">{item}</li>
                          ))}
                        </ul>
                      )}
                      {section.lien && (
                        <Link to={section.lien} data-testid={`ae-audit-lien-${key}`}>
                          Voir l&apos;écran
                        </Link>
                      )}
                    </section>
                  )
                })}
            </div>
          )}
        </div>
      )}
    </div>
  )
}
