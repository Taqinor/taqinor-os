import { useEffect, useState, useCallback } from 'react'
import { SlidersHorizontal, AlertTriangle, Play, Power, PowerOff } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  normalizeRuleTemplate, normalizeDryRun, normalizeAnomalies, normalizeAlerts,
  alertTone,
} from './adsengine'
import { formatDateTime } from '../../lib/format'
import AlertCenter from './AlertCenter'
import CommandPalette from './CommandPalette'

/* ============================================================================
   PUB23 — Armer/désarmer une règle depuis la console.
   ----------------------------------------------------------------------------
   Le catalogue (ci-dessus) reste un PICKER en lecture (templates statiques) ;
   l'état ARMÉ/DÉSARMÉ vit sur une instance ``RulePolicy`` par (société,
   template) — CRUD déjà exposé par ``RulePolicyViewSet`` (``regles/``), aucune
   route nouvelle. « Armer » = crée (si absente) ou met à jour l'instance en
   ``enabled=true, dry_run=false`` — la règle passe alors en évaluation
   PÉRIODIQUE réelle, mais reste en mode ``propose`` par défaut : elle ne fait
   QUE déposer des propositions dans la boîte d'approbation, jamais d'écriture
   directe (règle #3). « Désarmer » repose l'instance sur son défaut sûr
   (``enabled=false, dry_run=true``). Cadence FR affichée = celle du gabarit
   (catalogue/dd-guardian), pas un recalcul local.
   ========================================================================== */
const CADENCE_LABELS_FR = {
  critical: 'Toutes les 6 h (critique)',
  daily: 'Quotidienne',
  weekly: 'Hebdomadaire',
}
function cadenceLabel(cadence) {
  return CADENCE_LABELS_FR[cadence] || cadence || '—'
}

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
  const [journal, setJournal] = useState([]) // ADSDEEP43 — journal d'exécution enrichi
  const [loading, setLoading] = useState(true)
  const [dryRuns, setDryRuns] = useState({}) // key → { resume_fr, objets_touches }
  const [busyKey, setBusyKey] = useState(null)
  const [err, setErr] = useState('')
  // PUB23 — instances RulePolicy réelles (état armé/désarmé) + armement.
  const [policies, setPolicies] = useState([])
  const [confirmKey, setConfirmKey] = useState(null) // template en attente de confirmation d'armement
  const [armBusyKey, setArmBusyKey] = useState(null)
  const [armErr, setArmErr] = useState('')

  const reloadPolicies = useCallback(() => (
    adsengineApi.rules.list()
      .then(r => setPolicies(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setPolicies([]))
  ), [])

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
    // ADSDEEP43 — journal d'exécution enrichi (le « pourquoi » de chaque passe).
    adsengineApi.rules.journal()
      .then(r => setJournal(Array.isArray(r.data?.results) ? r.data.results : []))
      .catch(() => setJournal([]))
    reloadPolicies()
  }, [reloadPolicies])

  const policyFor = (key) => policies.find(p => p.template_key === key) || null

  const doArm = async (t) => {
    setArmBusyKey(t.key); setArmErr('')
    try {
      const existing = policyFor(t.key)
      if (existing) {
        await adsengineApi.rules.update(existing.id, { enabled: true, dry_run: false })
      } else {
        await adsengineApi.rules.create({
          template_key: t.key, enabled: true, dry_run: false })
      }
      setConfirmKey(null)
      await reloadPolicies()
    } catch {
      setArmErr("Armement refusé (permission « adsengine_manage » ?).")
    } finally {
      setArmBusyKey(null)
    }
  }

  const doDisarm = async (t) => {
    const existing = policyFor(t.key)
    if (!existing) return
    setArmBusyKey(t.key); setArmErr('')
    try {
      await adsengineApi.rules.update(existing.id, { enabled: false, dry_run: true })
      await reloadPolicies()
    } catch {
      setArmErr("Désarmement refusé (permission « adsengine_manage » ?).")
    } finally {
      setArmBusyKey(null)
    }
  }

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
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <SlidersHorizontal size={20} aria-hidden="true" /> Règles &amp; anomalies
        </h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          {/* PUB48 — centre de notifications persistant de la console */}
          <AlertCenter />
          {/* PUB51 — palette de commandes (Ctrl-K) */}
          <CommandPalette />
        </div>
      </div>

      {err && <p data-testid="ae-rules-err" style={{ color: '#dc2626' }}>{err}</p>}
      {armErr && <p data-testid="ae-rules-arm-err" style={{ color: '#dc2626' }}>{armErr}</p>}

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
                    const policy = policyFor(t.key)
                    const armed = !!(policy && policy.enabled)
                    return (
                      <article key={t.key} className="card ae-rule-template" data-testid="ae-rule-template"
                        style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: '0.6rem', flexWrap: 'wrap' }}>
                          <strong>{t.nom}</strong>
                          {/* PUB23 — état ARMÉ/DÉSARMÉ, toujours visible */}
                          <span className="badge" data-testid={`ae-rule-state-${t.key}`}
                            style={armed
                              ? { background: '#dcfce7', color: '#166534' }
                              : { background: '#f1f5f9', color: '#475569' }}>
                            {armed ? `Armée · ${cadenceLabel(t.cadence)}` : 'Désarmée'}
                          </span>
                          <div style={{ marginLeft: 'auto', display: 'flex', gap: '0.4rem' }}>
                            {armed ? (
                              <button type="button" className="btn btn-danger-outline ae-rule-disarm"
                                data-testid={`ae-rule-disarm-${t.key}`} disabled={armBusyKey === t.key}
                                onClick={() => doDisarm(t)}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                <PowerOff size={14} aria-hidden="true" /> Désarmer
                              </button>
                            ) : (
                              <button type="button" className="btn btn-light ae-rule-arm"
                                data-testid={`ae-rule-arm-${t.key}`} disabled={armBusyKey === t.key}
                                onClick={() => setConfirmKey(t.key)}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                <Power size={14} aria-hidden="true" /> Armer
                              </button>
                            )}
                            <button type="button" className="btn btn-primary"
                              data-testid={`ae-rule-dryrun-${t.key}`} disabled={busyKey === t.key}
                              onClick={() => dryRun(t.key)}
                              style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                              <Play size={14} aria-hidden="true" /> Simuler (dry-run)
                            </button>
                          </div>
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

                        {/* PUB23 — confirmation d'armement : résumé de la règle + cadence */}
                        {confirmKey === t.key && (
                          <div className="ae-rule-arm-confirm" data-testid={`ae-rule-arm-confirm-${t.key}`}
                            style={{ marginTop: '0.6rem', background: '#fffbeb', border: '1px solid #fde68a',
                              borderRadius: 6, padding: '0.75rem' }}>
                            <p style={{ margin: '0 0 0.5rem' }}>
                              Armer <strong>{t.nom}</strong> ? La règle sera évaluée <strong>{cadenceLabel(t.cadence)}</strong> et
                              ne fera que PROPOSER une action (SI {t.condition_fr} ALORS {t.action_fr}) —
                              toujours soumise à approbation.
                            </p>
                            <div style={{ display: 'flex', gap: '0.5rem' }}>
                              <button type="button" className="btn btn-primary ae-rule-arm-confirm-btn"
                                data-testid={`ae-rule-arm-confirm-btn-${t.key}`} disabled={armBusyKey === t.key}
                                onClick={() => doArm(t)}>
                                Confirmer l&apos;armement
                              </button>
                              <button type="button" className="btn btn-light"
                                onClick={() => setConfirmKey(null)}>Annuler</button>
                            </div>
                          </div>
                        )}

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

          {/* ── ADSDEEP43 — Journal d'exécution ENRICHI (le « pourquoi ») ── */}
          <section className="ae-rules-journal" data-testid="ae-rules-journal">
            <h3 style={{ margin: '0 0 0.6rem' }}>Journal d&apos;exécution</h3>
            {journal.length === 0
              ? <p data-testid="ae-rules-journal-empty" style={{ color: '#64748b' }}>
                  Aucune règle évaluée pour l&apos;instant.</p>
              : (
                <div style={{ display: 'grid', gap: '0.6rem' }}>
                  {journal.map(j => (
                    <article key={j.id} className="card ae-rule-run" data-testid="ae-rule-run"
                      style={{ padding: '0.85rem', border: '1px solid #e2e8f0' }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem', flexWrap: 'wrap' }}>
                        <strong>{j.label_fr}</strong>
                        {j.dry_run && (
                          <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>Simulation</span>
                        )}
                        <span className="badge" data-testid="ae-rule-run-verdict"
                          style={j.fired
                            ? { background: '#fee2e2', color: '#b91c1c' }
                            : { background: '#dcfce7', color: '#166534' }}>
                          {j.fired ? 'Déclenchée' : (j.evaluated ? 'Sans déclenchement' : 'Non câblée')}
                        </span>
                        {j.last_evaluated_at && (
                          <span style={{ marginLeft: 'auto', color: '#94a3b8', fontSize: '0.8rem' }}>
                            {formatDateTime(j.last_evaluated_at)}
                          </span>
                        )}
                      </div>
                      {(j.findings || []).length === 0
                        ? <p style={{ margin: '0.35rem 0 0', color: '#64748b', fontSize: '0.9rem' }}>
                            Aucune entité surveillée sur la dernière passe.</p>
                        : (
                          <ul style={{ listStyle: 'none', margin: '0.5rem 0 0', padding: 0, display: 'grid', gap: '0.4rem' }}>
                            {(j.findings || []).map((f, i) => (
                              <li key={`${j.id}-${f.target || i}`} data-testid="ae-rule-run-finding"
                                style={{ background: '#f8fafc', borderRadius: 6, padding: '0.5rem 0.6rem' }}>
                                <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'baseline', flexWrap: 'wrap' }}>
                                  <strong style={{ fontSize: '0.85rem' }}>{f.target || '—'}</strong>
                                  <span style={{ color: '#334155', fontSize: '0.85rem' }}>{f.condition_fr || '—'}</span>
                                </div>
                                {f.action && (
                                  <div data-testid="ae-rule-run-delta"
                                    style={{ marginTop: '0.3rem', color: '#5b21b6', fontSize: '0.82rem' }}>
                                    Action proposée : {f.action.reason_fr}
                                    {f.action.delta?.type === 'budget'
                                      && ` (${f.action.delta.current_mad ?? '?'} → ${f.action.delta.new_mad} MAD/j)`}
                                  </div>
                                )}
                              </li>
                            ))}
                          </ul>
                        )}
                    </article>
                  ))}
                </div>
              )}
          </section>
        </div>
      )}
    </div>
  )
}
