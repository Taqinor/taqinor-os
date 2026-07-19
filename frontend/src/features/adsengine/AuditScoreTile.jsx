import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { ShieldCheck, TrendingUp, TrendingDown } from 'lucide-react'
import adsengineApi from './adsengineApi'
import MetricHelp from './MetricHelp'

/* ============================================================================
   PUB57 — Tuile Dashboard « score d'audit », auto-chargée + delta hebdo.
   ----------------------------------------------------------------------------
   L'audit de compte (ADSDEEP63, `reporting/audit/`) vivait enterré en 3ᵉ
   onglet de Reporting, jamais ouvert d'initiative — cette tuile le rend
   visible SANS clic depuis le Dashboard. Réutilise le MÊME endpoint (déjà
   construit, additif : le backend y ajoute `score_tile` à côté des 5
   sections existantes) — aucune route nouvelle, aucun recalcul côté front.
   Fichier AUTONOME + un seul point de montage (`<AuditScoreTile />`) pour ne
   pas toucher le corps de DashboardScreen au-delà d'une ligne (lane
   partagée cette vague).
   ========================================================================== */
export default function AuditScoreTile() {
  const [tile, setTile] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState(false)

  const load = useCallback(() => {
    setLoading(true); setErr(false)
    adsengineApi.reports.audit()
      .then(r => setTile(r.data?.score_tile || null))
      .catch(() => setErr(true))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="card ae-audit-score-tile" data-testid="ae-audit-score-tile"
        style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
        <p className="page-loading" style={{ margin: 0 }}>Chargement…</p>
      </div>
    )
  }
  if (err || !tile) {
    return (
      <div className="card ae-audit-score-tile" data-testid="ae-audit-score-tile"
        style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
        <p data-testid="ae-audit-score-tile-error" style={{ margin: 0, color: '#64748b', fontSize: '0.85rem' }}>
          Score d&apos;audit indisponible pour le moment.
        </p>
      </div>
    )
  }

  const { score, ok_count: okCount, total_sections: totalSections, delta_hebdo: deltaHebdo } = tile
  const deltaUp = deltaHebdo != null && deltaHebdo > 0
  const deltaDown = deltaHebdo != null && deltaHebdo < 0

  return (
    <Link to="/publicite/reporting" className="card ae-audit-score-tile" data-testid="ae-audit-score-tile"
      style={{ padding: '1rem', border: '1px solid #e2e8f0', display: 'block', textDecoration: 'none', color: 'inherit' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: '0.4rem', color: '#64748b', fontSize: '0.85rem' }}>
        <ShieldCheck size={15} aria-hidden="true" />
        Score d&apos;audit de compte
        <MetricHelp metric="quality_ranking" label="Score d'audit de compte" />
      </div>
      <div style={{ display: 'flex', alignItems: 'baseline', gap: '0.5rem', marginTop: '0.2rem' }}>
        <span data-testid="ae-audit-score-tile-value" style={{ fontSize: '2rem', fontWeight: 700 }}>
          {score == null ? '—' : `${score}/100`}
        </span>
        {deltaHebdo != null && (
          <span data-testid="ae-audit-score-tile-delta"
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.2rem', fontSize: '0.85rem',
              color: deltaUp ? '#15803d' : deltaDown ? '#b91c1c' : '#64748b' }}>
            {deltaUp && <TrendingUp size={14} aria-hidden="true" />}
            {deltaDown && <TrendingDown size={14} aria-hidden="true" />}
            {deltaHebdo > 0 ? '+' : ''}{deltaHebdo} vs il y a 7 j
          </span>
        )}
      </div>
      {score != null && (
        <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.2rem' }}>
          {okCount}/{totalSections} sections OK — voir le détail →
        </div>
      )}
    </Link>
  )
}
