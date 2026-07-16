import { useEffect, useState, useCallback } from 'react'
import { SlidersHorizontal, AlertTriangle, Play } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeRuleTemplate, normalizeDryRun, normalizeAnomalies, normalizeAlerts,
  alertTone,
} from './adsengine'

/* ============================================================================
   ENG43 — Écran « Règles & anomalies ».
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md, domaines 2 & 8) : on NE construit PAS un DSL de
   règles from-scratch (Meta donne déjà des règles natives). On offre un
   CATALOGUE DE GABARITS FR — un PICKER, jamais un builder libre : chaque gabarit
   dit en clair « condition FR → action FR ». Avant d'armer une règle, on la
   SIMULE (dry-run) : la liste des objets qui seraient touchés + l'effet, sans
   rien appliquer. À côté, le flux d'ANOMALIES (ENG16) avec sévérités et
   l'HISTORIQUE des alertes (ENG13). Tous les nombres/objets = ceux de l'API.
   ========================================================================== */

export default function RulesScreen() {
  const [templates, setTemplates] = useState([])
  const [anomalies, setAnomalies] = useState([])
  const [history, setHistory] = useState([])
  const [loading, setLoading] = useState(true)
  const [dryRuns, setDryRuns] = useState({}) // key → { resume_fr, objets_touches }
  const [busyKey, setBusyKey] = useState(null)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.rules.templates()
      .then(r => setTemplates((Array.isArray(r.data) ? r.data : (r.data?.results || []))
        .map(normalizeRuleTemplate)))
      .catch(() => setTemplates([]))
    adsengineApi.anomalies.list()
      .then(r => setAnomalies(normalizeAnomalies(r.data)))
      .catch(() => setAnomalies([]))
    adsengineApi.alerts.history()
      .then(r => setHistory(normalizeAlerts(r.data)))
      .catch(() => setHistory([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // Dry-run d'un gabarit : simule, ne modifie RIEN.
  const dryRun = async (key) => {
    setBusyKey(key); setErr('')
    try {
      const r = await adsengineApi.rules.dryRun(key)
      setDryRuns(m => ({ ...m, [key]: normalizeDryRun(r.data) }))
    } catch {
      setErr('Simulation impossible.')
    } finally {
      setBusyKey(null)
    }
  }

  return (
    <div className="page ae-rules">
      <div className="page-header">
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <SlidersHorizontal size={20} aria-hidden="true" /> Règles &amp; anomalies
        </h2>
      </div>

      {err && <p data-testid="ae-rules-err" style={{ color: '#dc2626' }}>{err}</p>}

      {loading ? <p className="page-loading">Chargement…</p> : (
        <div style={{ display: 'grid', gap: '1.25rem' }}>
          {/* ── Catalogue de gabarits (PICKER) ── */}
          <section className="ae-rules-catalogue" data-testid="ae-rules-catalogue">
            <h3 style={{ margin: '0 0 0.6rem' }}>Catalogue de gabarits</h3>
            {templates.length === 0
              ? <p data-testid="ae-rules-empty" style={{ color: '#64748b' }}>
                  Aucun gabarit disponible.</p>
              : (
                <div style={{ display: 'grid', gap: '0.75rem' }}>
                  {templates.map(t => {
                    const dr = dryRuns[t.key]
                    return (
                      <article key={t.key} className="card ae-rule-template" data-testid="ae-rule-template"
                        style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                          <strong>{t.nom}</strong>
                          <button type="button" className="btn btn-primary"
                            data-testid={`ae-rule-dryrun-${t.key}`} disabled={busyKey === t.key}
                            onClick={() => dryRun(t.key)}
                            style={{ marginLeft: 'auto', display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                            <Play size={14} aria-hidden="true" /> Simuler (dry-run)
                          </button>
                        </div>
                        {t.description && (
                          <p style={{ margin: '0.3rem 0 0.5rem', color: '#64748b', fontSize: '0.9rem' }}>{t.description}</p>
                        )}
                        {/* Condition FR → action FR, en clair */}
                        <p style={{ margin: 0, color: '#334155' }}>
                          <span className="badge" style={{ background: '#e0f2fe', color: '#075985' }}>SI</span>{' '}
                          {t.condition_fr || '—'}{' '}
                          <span className="badge" style={{ background: '#ede9fe', color: '#5b21b6' }}>ALORS</span>{' '}
                          {t.action_fr || '—'}
                        </p>

                        {/* Résultat du dry-run — VISUALISÉ */}
                        {dr && (
                          <div className="ae-rule-dryrun-result" data-testid={`ae-rule-dryrun-result-${t.key}`}
                            style={{ marginTop: '0.75rem', background: '#f8fafc', borderRadius: 6, padding: '0.75rem' }}>
                            <p style={{ margin: '0 0 0.4rem', fontWeight: 600 }}>
                              Simulation — {dr.resume_fr || `${dr.objets_touches.length} objet(s) touché(s)`}
                            </p>
                            {dr.objets_touches.length === 0
                              ? <p style={{ margin: 0, color: '#64748b' }}>Aucun objet ne serait touché.</p>
                              : (
                                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.35rem' }}>
                                  {dr.objets_touches.map(o => (
                                    <li key={o.id} data-testid="ae-rule-dryrun-object"
                                      style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline' }}>
                                      <strong>{o.nom}</strong>
                                      <span style={{ color: '#475569' }}>{o.effet_fr}</span>
                                    </li>
                                  ))}
                                </ul>
                              )}
                          </div>
                        )}
                      </article>
                    )
                  })}
                </div>
              )}
          </section>

          {/* ── Flux d'anomalies (ENG16) ── */}
          <section className="ae-anomalies" data-testid="ae-anomalies">
            <h3 style={{ margin: '0 0 0.6rem' }}>Anomalies détectées</h3>
            {anomalies.length === 0
              ? <p data-testid="ae-anomalies-empty" style={{ color: '#64748b' }}>
                  Aucune anomalie détectée.</p>
              : (
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
                  {anomalies.map(a => {
                    const tone = alertTone(a.severite)
                    return (
                      <li key={a.id} className="card ae-anomaly" data-testid="ae-anomaly"
                        style={{ padding: '0.75rem', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                          <AlertTriangle size={15} aria-hidden="true" style={{ color: tone.color }} />
                          <strong>{a.titre}</strong>
                          <span className="badge" data-testid="ae-anomaly-severity"
                            style={{ background: tone.bg, color: tone.color }}>{tone.label}</span>
                          {a.quand && (
                            <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>{a.quand}</span>
                          )}
                        </div>
                        {a.message && <p style={{ margin: '0.3rem 0 0', color: '#334155' }}>{a.message}</p>}
                      </li>
                    )
                  })}
                </ul>
              )}
          </section>

          {/* ── Historique des alertes (ENG13) ── */}
          <section className="ae-alert-history" data-testid="ae-alert-history">
            <h3 style={{ margin: '0 0 0.6rem' }}>Historique des alertes</h3>
            {history.length === 0
              ? <p data-testid="ae-alert-history-empty" style={{ color: '#64748b' }}>
                  Aucune alerte passée.</p>
              : (
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.4rem' }}>
                  {history.map((h, i) => {
                    const tone = alertTone(h.niveau)
                    return (
                      <li key={h.id ?? i} data-testid="ae-alert-history-row"
                        style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                          padding: '0.4rem 0.6rem', background: '#f8fafc', borderRadius: 6 }}>
                        <span className="badge" style={{ background: tone.bg, color: tone.color }}>{tone.label}</span>
                        <span>{h.message || h.titre}</span>
                        {h.quand && (
                          <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>{h.quand}</span>
                        )}
                      </li>
                    )
                  })}
                </ul>
              )}
          </section>
        </div>
      )}
    </div>
  )
}
