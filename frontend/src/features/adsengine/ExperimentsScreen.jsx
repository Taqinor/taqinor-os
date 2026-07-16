import { useEffect, useState, useMemo, useCallback } from 'react'
import { FlaskConical, Trophy } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeExperiment, normalizeDecisionLog, filterDecisionLog, bestArm,
  formatPercent, formatMAD, formatRatio, formatNumber,
} from './adsengine'

/* ============================================================================
   ENG39 — Écran « Expérimentations » (moteur bandit).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md, domaine 3 — A/B testing traçable) : rendre les
   POSTERIORS lisibles par un NON-statisticien. Pour chaque bras :
   - P(meilleur) — la probabilité, en clair, que ce bras soit le gagnant ;
   - l'estimation (moyenne) + une BANDE DE CRÉDIBILITÉ visualisée [bas ; haut] ;
   - la part de budget allouée par le moteur.
   Le DecisionLog est rendu « pourquoi le moteur a fait X » en phrases FR + les
   chiffres exacts, filtrable par phase. TOUS les nombres viennent de l'API ENG12
   (mockée en test) — rien n'est calculé ni inventé ici.
   ========================================================================== */

// Formate une valeur métier selon le format de la métrique de l'expérimentation.
function fmtMetric(fmt, value) {
  if (fmt === 'ratio') return formatRatio(value)
  if (fmt === 'percent') return formatPercent(value)
  return formatMAD(value)
}

// Tons de statut de phase (déterministes, FR).
function phaseTone(statut) {
  const s = String(statut || '').toLowerCase()
  if (s.startsWith('termin')) return { bg: '#dcfce7', color: '#166534' }
  if (s.startsWith('en_cours') || s.startsWith('en cours')) return { bg: '#e0f2fe', color: '#075985' }
  return { bg: '#f1f5f9', color: '#64748b' }
}

export default function ExperimentsScreen() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [current, setCurrent] = useState(null) // expérimentation normalisée
  const [log, setLog] = useState([])
  const [phaseFilter, setPhaseFilter] = useState('')
  const [selectedId, setSelectedId] = useState(null)

  // Charge le détail + le DecisionLog d'une expérimentation.
  const loadDetail = useCallback((id) => {
    setSelectedId(id)
    setPhaseFilter('')
    adsengineApi.experiments.get(id)
      .then(r => setCurrent(normalizeExperiment(r.data)))
      .catch(() => setCurrent(null))
    adsengineApi.experiments.decisionLog(id)
      .then(r => setLog(normalizeDecisionLog(r.data)))
      .catch(() => setLog([]))
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.experiments.list()
      .then(r => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        setList(rows)
        if (rows.length) loadDetail(rows[0].id)
      })
      .catch(() => setList([]))
      .finally(() => setLoading(false))
  }, [loadDetail])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const visibleLog = useMemo(
    () => filterDecisionLog(log, { phase: phaseFilter }), [log, phaseFilter])

  const best = current ? bestArm(current.bras) : null

  // Échelle des bandes de crédibilité (présentation seule, aria-hidden).
  const bounds = useMemo(() => {
    const vals = (current?.bras || [])
      .flatMap(b => [b.ci_low, b.ci_high, b.mean])
      .filter(v => Number.isFinite(v))
    if (!vals.length) return null
    const min = Math.min(...vals); const max = Math.max(...vals)
    return { min, max, span: max - min || 1 }
  }, [current])

  const bandStyle = (b) => {
    if (!bounds || !Number.isFinite(b.ci_low) || !Number.isFinite(b.ci_high)) return null
    const left = ((b.ci_low - bounds.min) / bounds.span) * 100
    const width = ((b.ci_high - b.ci_low) / bounds.span) * 100
    return { left: `${left}%`, width: `${Math.max(width, 2)}%` }
  }

  return (
    <div className="page ae-experiments" data-testid="ae-experiments">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <FlaskConical size={20} aria-hidden="true" /> Expérimentations
        </h2>
      </div>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : list.length === 0
          ? <p data-testid="ae-exp-empty" style={{ color: '#64748b' }}>
              Aucune expérimentation en cours.</p>
          : (
            <>
              {/* Sélecteur d'expérimentation */}
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}
                data-testid="ae-exp-list" role="group" aria-label="Choisir une expérimentation">
                {list.map(e => (
                  <button key={e.id} type="button"
                    className={`btn ${selectedId === e.id ? 'btn-primary' : 'btn-light'}`}
                    data-testid={`ae-exp-select-${e.id}`}
                    aria-pressed={selectedId === e.id}
                    onClick={() => loadDetail(e.id)}>
                    {e.nom || e.name || `Expérimentation ${e.id}`}
                  </button>
                ))}
              </div>

              {current && (
                <>
                  {/* Timeline des phases */}
                  <section className="card ae-exp-phases" data-testid="ae-exp-phases"
                    style={{ padding: '1rem', marginBottom: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Phases</h3>
                    <ol style={{ listStyle: 'none', margin: 0, padding: 0, display: 'flex',
                      gap: '0.5rem', flexWrap: 'wrap' }}>
                      {current.phases.length === 0
                        ? <li style={{ color: '#64748b' }}>Aucune phase définie.</li>
                        : current.phases.map(p => {
                          const tone = phaseTone(p.statut)
                          return (
                            <li key={p.key} data-testid="ae-exp-phase"
                              style={{ display: 'flex', alignItems: 'center', gap: '0.4rem',
                                background: tone.bg, color: tone.color,
                                padding: '0.4rem 0.7rem', borderRadius: 999 }}>
                              <strong>{p.label}</strong>
                              <span style={{ fontSize: '0.8rem' }}>· {p.statut_display || '—'}</span>
                            </li>
                          )
                        })}
                    </ol>
                  </section>

                  {/* Bras avec posteriors visualisés */}
                  <section className="card ae-exp-arms" data-testid="ae-exp-arms"
                    style={{ padding: '1rem', marginBottom: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.75rem' }}>
                      Bras — {current.metrique_label} (P(meilleur) + bande de crédibilité)
                    </h3>
                    <div style={{ display: 'grid', gap: '0.9rem' }}>
                      {current.bras.map(b => {
                        const isBest = best && b.id === best.id
                        const bs = bandStyle(b)
                        return (
                          <article key={b.id} data-testid="ae-exp-arm"
                            style={{ border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.75rem',
                              background: isBest ? '#f0fdf4' : '#fff' }}>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                              flexWrap: 'wrap' }}>
                              <strong>{b.nom}</strong>
                              {isBest && (
                                <span className="badge" data-testid="ae-exp-arm-best"
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                                    background: '#dcfce7', color: '#166534' }}>
                                  <Trophy size={13} aria-hidden="true" /> Favori du moteur
                                </span>
                              )}
                              <span style={{ marginLeft: 'auto', color: '#64748b', fontSize: '0.85rem' }}>
                                Allocation {formatPercent(b.allocation)}
                              </span>
                            </div>

                            {/* P(meilleur) — la probabilité, en clair */}
                            <p style={{ margin: '0.4rem 0 0.2rem' }}>
                              Probabilité d&apos;être le meilleur :{' '}
                              <strong data-testid={`ae-exp-pbest-${b.id}`}>{formatPercent(b.p_best)}</strong>
                            </p>

                            {/* Estimation + bande de crédibilité (numérique + barre) */}
                            <p style={{ margin: '0 0 0.4rem', color: '#334155', fontSize: '0.9rem' }}>
                              Estimation :{' '}
                              <strong data-testid={`ae-exp-mean-${b.id}`}>
                                {fmtMetric(current.metrique_fmt, b.mean)}
                              </strong>
                              {' '}(intervalle{' '}
                              <span data-testid={`ae-exp-band-${b.id}`}>
                                {fmtMetric(current.metrique_fmt, b.ci_low)} – {fmtMetric(current.metrique_fmt, b.ci_high)}
                              </span>)
                            </p>
                            {bs && (
                              <div aria-hidden="true" style={{ position: 'relative', height: 8,
                                background: '#f1f5f9', borderRadius: 999 }}>
                                <div style={{ position: 'absolute', top: 0, bottom: 0, ...bs,
                                  background: isBest ? '#22c55e' : '#94a3b8', borderRadius: 999 }} />
                              </div>
                            )}
                          </article>
                        )
                      })}
                    </div>
                  </section>

                  {/* DecisionLog — « pourquoi le moteur a fait X » (FR + chiffres) */}
                  <section className="card ae-exp-decisions" data-testid="ae-exp-decisions"
                    style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '0.75rem',
                      flexWrap: 'wrap', marginBottom: '0.6rem' }}>
                      <h3 style={{ margin: 0 }}>Journal des décisions</h3>
                      <label style={{ display: 'flex', alignItems: 'center', gap: '0.4rem',
                        marginLeft: 'auto' }}>
                        <span style={{ fontSize: '0.85rem', color: '#475569' }}>Phase</span>
                        <select className="form-input" data-testid="ae-exp-decision-filter"
                          value={phaseFilter} onChange={e => setPhaseFilter(e.target.value)}
                          style={{ flex: '0 1 200px' }}>
                          <option value="">Toutes les phases</option>
                          {current.phases.map(p => (
                            <option key={p.key} value={p.key}>{p.label}</option>
                          ))}
                        </select>
                      </label>
                    </div>
                    {visibleLog.length === 0
                      ? <p data-testid="ae-exp-decisions-empty" style={{ color: '#64748b' }}>
                          Aucune décision pour ce filtre.</p>
                      : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
                          {visibleLog.map(d => (
                            <li key={d.id} className="ae-exp-decision" data-testid="ae-exp-decision"
                              style={{ borderLeft: '3px solid #cbd5e1', paddingLeft: '0.75rem' }}>
                              <p style={{ margin: 0, color: '#1e293b' }}>{d.decision_fr}</p>
                              <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap',
                                marginTop: '0.3rem' }}>
                                {Object.entries(d.chiffres).map(([k, v]) => (
                                  <span key={k} className="badge" data-testid="ae-exp-decision-figure"
                                    style={{ background: '#f1f5f9', color: '#475569' }}>
                                    {k} : {typeof v === 'number' ? formatNumber(v, Number.isInteger(v) ? 0 : 1) : String(v)}
                                  </span>
                                ))}
                                {(d.phase_label || d.quand) && (
                                  <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>
                                    {d.phase_label}{d.phase_label && d.quand ? ' · ' : ''}{d.quand}
                                  </span>
                                )}
                              </div>
                            </li>
                          ))}
                        </ul>
                      )}
                  </section>
                </>
              )}
            </>
          )}
    </div>
  )
}
