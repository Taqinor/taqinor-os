import { useEffect, useState, useCallback } from 'react'
import { MonitorPlay } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeSimReport, verdictTone, formatMAD, formatNumber } from './adsengine'

/* ============================================================================
   ENG44 — Visionneuse de simulation (rejeu visuel d'un run ADSENG36).
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md) : c'est l'OUTIL DE CONFIANCE FONDATEUR — avant
   d'engager un seul dirham réel, on REJOUE la simulation visuellement :
   - les ALLOCATIONS dans le temps (budget par bras à chaque étape) ;
   - les DÉCISIONS annotées (« pourquoi le moteur a réalloué », FR + chiffres) ;
   - le VERDICT par scénario (gagnant / perdant / neutre).
   Aucun chiffre n'est calculé ici : tout vient du rapport de simulation ENG36.
   ========================================================================== */

// Somme des budgets d'une étape (pour les proportions de la barre empilée).
function stepTotal(bras) {
  return (bras || []).reduce((s, b) => s + (Number.isFinite(b.budget_mad) ? b.budget_mad : 0), 0)
}

const SEGMENT_COLORS = ['#2563eb', '#16a34a', '#d97706', '#7c3aed', '#dc2626', '#0891b2']

export default function SimulationScreen() {
  const [list, setList] = useState([])
  const [loading, setLoading] = useState(true)
  const [report, setReport] = useState(null)
  const [selectedId, setSelectedId] = useState(null)

  const loadReport = useCallback((id) => {
    setSelectedId(id)
    adsengineApi.simulations.get(id)
      .then(r => setReport(normalizeSimReport(r.data)))
      .catch(() => setReport(null))
  }, [])

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.simulations.list()
      .then(r => {
        const rows = Array.isArray(r.data) ? r.data : (r.data?.results || [])
        setList(rows)
        if (rows.length) loadReport(rows[0].id)
      })
      .catch(() => setList([]))
      .finally(() => setLoading(false))
  }, [loadReport])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  return (
    <div className="page ae-simulation">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <MonitorPlay size={20} aria-hidden="true" /> Visionneuse de simulation
        </h2>
      </div>

      {loading
        ? <p className="page-loading">Chargement…</p>
        : list.length === 0
          ? <p data-testid="ae-sim-empty" style={{ color: '#64748b' }}>
              Aucune simulation à rejouer.</p>
          : (
            <>
              {/* Sélecteur de run */}
              <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginBottom: '1rem' }}
                data-testid="ae-sim-runs" role="group" aria-label="Choisir une simulation">
                {list.map(s => (
                  <button key={s.id} type="button"
                    className={`btn ${selectedId === s.id ? 'btn-primary' : 'btn-light'}`}
                    data-testid={`ae-sim-run-${s.id}`} aria-pressed={selectedId === s.id}
                    onClick={() => loadReport(s.id)}>
                    {s.nom || s.name || `Simulation ${s.id}`}
                    {s.cree_le ? ` · ${s.cree_le}` : ''}
                  </button>
                ))}
              </div>

              {report && (
                <div data-testid="ae-sim-report" style={{ display: 'grid', gap: '1rem' }}>
                  {/* Verdicts par scénario */}
                  <section className="card ae-sim-scenarios" data-testid="ae-sim-scenarios"
                    style={{ padding: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Verdict par scénario</h3>
                    {report.scenarios.length === 0
                      ? <p style={{ color: '#64748b', margin: 0 }}>Aucun scénario.</p>
                      : (
                        <div style={{ display: 'grid', gap: '0.5rem' }}>
                          {report.scenarios.map(sc => {
                            const tone = verdictTone(sc.verdict)
                            return (
                              <div key={sc.key} data-testid="ae-sim-scenario"
                                style={{ display: 'flex', alignItems: 'center', gap: '0.6rem',
                                  flexWrap: 'wrap', border: '1px solid #e2e8f0', borderRadius: 6, padding: '0.6rem 0.75rem' }}>
                                <strong>{sc.nom}</strong>
                                <span className="badge" data-testid="ae-sim-verdict"
                                  style={{ background: tone.bg, color: tone.color }}>{sc.verdict_display}</span>
                                {sc.resume_fr && (
                                  <span style={{ color: '#475569', flex: '1 1 100%' }}>{sc.resume_fr}</span>
                                )}
                              </div>
                            )
                          })}
                        </div>
                      )}
                  </section>

                  {/* Allocations dans le temps */}
                  <section className="card ae-sim-allocations" data-testid="ae-sim-allocations"
                    style={{ padding: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Allocations dans le temps</h3>
                    {report.allocations.length === 0
                      ? <p style={{ color: '#64748b', margin: 0 }}>Aucune allocation enregistrée.</p>
                      : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
                          {report.allocations.map((a, idx) => {
                            const total = stepTotal(a.bras) || 1
                            return (
                              <li key={idx} data-testid="ae-sim-step">
                                <div style={{ display: 'flex', justifyContent: 'space-between',
                                  fontSize: '0.85rem', color: '#475569', marginBottom: '0.25rem' }}>
                                  <span>{a.label}</span>
                                </div>
                                {/* Barre empilée (aria-hidden) */}
                                <div aria-hidden="true" style={{ display: 'flex', height: 10,
                                  borderRadius: 999, overflow: 'hidden', background: '#f1f5f9' }}>
                                  {a.bras.map((b, j) => (
                                    <div key={j} style={{ width: `${((b.budget_mad || 0) / total) * 100}%`,
                                      background: SEGMENT_COLORS[j % SEGMENT_COLORS.length] }} />
                                  ))}
                                </div>
                                {/* Légende chiffrée */}
                                <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap', marginTop: '0.3rem' }}>
                                  {a.bras.map((b, j) => (
                                    <span key={j} data-testid="ae-sim-arm-budget"
                                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                                        fontSize: '0.85rem', color: '#334155' }}>
                                      <span aria-hidden="true" style={{ width: 10, height: 10, borderRadius: 2,
                                        background: SEGMENT_COLORS[j % SEGMENT_COLORS.length] }} />
                                      {b.nom} : {formatMAD(b.budget_mad)}
                                    </span>
                                  ))}
                                </div>
                              </li>
                            )
                          })}
                        </ul>
                      )}
                  </section>

                  {/* Décisions annotées */}
                  <section className="card ae-sim-decisions" data-testid="ae-sim-decisions"
                    style={{ padding: '1rem' }}>
                    <h3 style={{ margin: '0 0 0.6rem' }}>Décisions annotées</h3>
                    {report.decisions.length === 0
                      ? <p style={{ color: '#64748b', margin: 0 }}>Aucune décision annotée.</p>
                      : (
                        <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.6rem' }}>
                          {report.decisions.map(d => (
                            <li key={d.id} data-testid="ae-sim-decision"
                              style={{ borderLeft: '3px solid #cbd5e1', paddingLeft: '0.75rem' }}>
                              {d.label && (
                                <span style={{ color: '#94a3b8', fontSize: '0.8rem' }}>{d.label}</span>
                              )}
                              <p style={{ margin: '0.1rem 0 0', color: '#1e293b' }}>{d.decision_fr}</p>
                              {Object.keys(d.chiffres).length > 0 && (
                                <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.3rem' }}>
                                  {Object.entries(d.chiffres).map(([k, v]) => (
                                    <span key={k} className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>
                                      {k} : {typeof v === 'number' ? formatNumber(v, Number.isInteger(v) ? 0 : 1) : String(v)}
                                    </span>
                                  ))}
                                </div>
                              )}
                            </li>
                          ))}
                        </ul>
                      )}
                  </section>
                </div>
              )}
            </>
          )}
    </div>
  )
}
