import { useEffect, useState, useMemo, useCallback } from 'react'
import { BarChart3, Download } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeVariants, normalizeFunnel, normalizeCohorts, normalizeLeaderboard,
  normalizeScatter, toCsv, formatMAD, formatNumber, formatPercent,
} from './adsengine'

/* ============================================================================
   ENG45 — Drill-downs reporting (consomme ENG33).
   ----------------------------------------------------------------------------
   Trois vues d'analyse fine + un export CSV :
   - TABLE des variantes (impressions, réponses WhatsApp, coût, coût/réponse) ;
   - ENTONNOIR de campagne (étapes ordonnées avec leur valeur) ;
   - COHORTES avec le lag médian jusqu'à la signature.
   L'export CSV est construit côté client à partir des variantes CHARGÉES (les
   mêmes chiffres que l'API — jamais inventés) et proposé en lien téléchargeable.

   ADSDEEP47 — un second ONGLET « Créatifs » : classement spend-weighted par
   hook/angle/format + nuage hook rate × dépense (quadrants FR « pépites
   cachées »/« gouffres »/« gagnants confirmés »/« à surveiller »), période
   sélectionnable (7/30/90 jours).
   ========================================================================== */

const CSV_HEADERS = ['Variante', 'Impressions', 'Réponses WhatsApp', 'Coût (MAD)', 'Coût par réponse (MAD)']

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

function periodParams(days) {
  const fin = new Date()
  const debut = new Date(fin)
  debut.setDate(debut.getDate() - (days - 1))
  const iso = (d) => d.toISOString().slice(0, 10)
  return { debut: iso(debut), fin: iso(fin) }
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

  // Export CSV : construit depuis les variantes chargées (data-URI, pas de dep).
  const csvHref = useMemo(() => {
    if (variants.length === 0) return null
    const rows = variants.map(v => [
      v.nom, v.impressions ?? '', v.reponses_whatsapp ?? '', v.cout_mad ?? '', v.cout_par_reponse ?? '',
    ])
    const csv = toCsv(CSV_HEADERS, rows)
    return `data:text/csv;charset=utf-8,${encodeURIComponent(csv)}`
  }, [variants])

  const funnelMax = useMemo(
    () => funnel.reduce((m, e) => Math.max(m, Number.isFinite(e.valeur) ? e.valeur : 0), 0) || 1,
    [funnel])

  return (
    <div className="page ae-reports">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <BarChart3 size={20} aria-hidden="true" /> Reporting
        </h2>
        {tab === 'apercu' && csvHref && (
          <a className="btn btn-primary" data-testid="ae-reports-export"
            href={csvHref} download="variantes-taqinor.csv"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <Download size={15} aria-hidden="true" /> Exporter en CSV
          </a>
        )}
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
      </div>

      {tab === 'apercu' && (
        loading ? <p className="page-loading">Chargement…</p> : (
          <div style={{ display: 'grid', gap: '1.25rem' }}>
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
                          <td>{v.nom}</td>
                          <td>{formatNumber(v.impressions)}</td>
                          <td>{formatNumber(v.reponses_whatsapp)}</td>
                          <td>{formatMAD(v.cout_mad)}</td>
                          <td>{formatMAD(v.cout_par_reponse)}</td>
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
                          <td>{c.cohorte}</td>
                          <td>{formatNumber(c.taille)}</td>
                          <td>{formatNumber(c.lag_jours_median)}</td>
                          <td>{formatNumber(c.signatures)}</td>
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
                          <th>Coût / résultat</th><th>Hook rate (pondéré)</th><th>Ads</th>
                        </tr>
                      </thead>
                      <tbody>
                        {leaderboard.classement.map(row => (
                          <tr key={row.id} data-testid="ae-creatifs-leaderboard-row">
                            <td>{row.tag}</td>
                            <td>{formatMAD(row.spend)}</td>
                            <td>{formatNumber(row.results)}</td>
                            <td>{formatMAD(row.costPerResult)}</td>
                            <td>{formatPercent(row.hookRateWeighted, 1)}</td>
                            <td>{formatNumber(row.adCount)}</td>
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
                        <tr><th>Ad</th><th>Dépense</th><th>Hook rate</th><th>Quadrant</th></tr>
                      </thead>
                      <tbody>
                        {scatter.points.map(p => (
                          <tr key={p.id} data-testid="ae-creatifs-scatter-row">
                            <td>{p.nom}</td>
                            <td>{formatMAD(p.spend)}</td>
                            <td>{formatPercent(p.hookRate, 1)}</td>
                            <td data-testid="ae-creatifs-scatter-quadrant">{p.quadrantLabel}</td>
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
    </div>
  )
}
