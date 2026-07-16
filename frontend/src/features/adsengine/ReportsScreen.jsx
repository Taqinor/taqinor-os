import { useEffect, useState, useMemo, useCallback } from 'react'
import { BarChart3, Download } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeVariants, normalizeFunnel, normalizeCohorts, toCsv,
  formatMAD, formatNumber,
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
   ========================================================================== */

const CSV_HEADERS = ['Variante', 'Impressions', 'Réponses WhatsApp', 'Coût (MAD)', 'Coût par réponse (MAD)']

export default function ReportsScreen() {
  const [variants, setVariants] = useState([])
  const [funnel, setFunnel] = useState([])
  const [cohorts, setCohorts] = useState([])
  const [loading, setLoading] = useState(true)

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

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

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
        {csvHref && (
          <a className="btn btn-primary" data-testid="ae-reports-export"
            href={csvHref} download="variantes-taqinor.csv"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.35rem' }}>
            <Download size={15} aria-hidden="true" /> Exporter en CSV
          </a>
        )}
      </div>

      {loading ? <p className="page-loading">Chargement…</p> : (
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
      )}
    </div>
  )
}
