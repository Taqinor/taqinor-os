import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Bell, ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'
import {
  formatMAD, formatMoney, formatRatio, formatPercent, normalizeAlerts,
  alertTone, normalizePacing, pacingStateTone, normalizeReconciliation,
  reconStatusTone,
} from './adsengine'

/* ============================================================================
   ENG23 — Dashboard « un chiffre » du moteur publicitaire.
   ----------------------------------------------------------------------------
   Doctrine (scope-features.md, domaine 7 — le plus fort levier) :
   - HÉRO = coût par signature (le seul chiffre qui compte pour une vente
     consultative — jamais ROAS/CPA).
   - Tuiles secondaires : dépense / coût par lead / fréquence.
   - Traçabilité Northbeam : CHAQUE chiffre est cliquable → la liste des LEADS
     RÉELS derrière (jamais de chiffre boîte-noire). Le clic appelle
     `metrics.leads(<clé>)` et ouvre le panneau de drill-down.
   - Bandeau d'alertes ENG13 (WhatsApp-first) en tête.
   Les nombres affichés sont EXCLUSIVEMENT ceux de l'API metrics — rien n'est
   calculé ni inventé ici.

   ENG42 — deux vues ADDITIVES sous forme d'onglets (pas de nouvel écran,
   dd-treasury §e) :
   - Pacing (ENG20) : enveloppe / burn / projection / état, chiffres cliquables
     vers le détail des dépenses.
   - Réconciliation (ENG31) : écart Meta-vs-ERP par campagne + statut, chaque
     ligne cliquable vers son détail. Ces vues sont chargées PARESSEUSEMENT (au
     clic sur l'onglet) — la vue d'ensemble reste inchangée.
   ========================================================================== */

// Définition des chiffres cliquables. `metric` = clé passée à metrics.leads().
// `fmt` = 'mad' (montant) | 'ratio' (décimal). Le héro est marqué `hero`.
const NUMBERS = [
  { key: 'cost_per_signature', metric: 'signature', label: 'Coût par signature', fmt: 'mad', hero: true },
  { key: 'spend', metric: 'spend', label: 'Dépense', fmt: 'mad' },
  { key: 'cpl', metric: 'lead', label: 'Coût par lead', fmt: 'mad' },
  { key: 'frequency', metric: 'frequency', label: 'Fréquence', fmt: 'ratio' },
]

// Les montants Meta (dépense, CPL, coût/signature) sont dans la devise du
// COMPTE publicitaire (`metrics.currency`, souvent USD) — jamais forcés en MAD.
function fmtValue(fmt, value, currency) {
  return fmt === 'ratio' ? formatRatio(value) : formatMoney(value, currency)
}

const TABS = [
  { key: 'overview', label: 'Vue d\'ensemble' },
  { key: 'pacing', label: 'Pacing' },
  { key: 'reconciliation', label: 'Réconciliation' },
]

export default function DashboardScreen() {
  const [metrics, setMetrics] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [drill, setDrill] = useState(null) // { metric, label }
  const [leads, setLeads] = useState([])
  const [leadsLoading, setLeadsLoading] = useState(false)

  // ENG42 — onglets Pacing / Réconciliation (chargés paresseusement).
  const [tab, setTab] = useState('overview')
  const [pacing, setPacing] = useState(null)
  const [pacingDetailOpen, setPacingDetailOpen] = useState(false)
  const [recon, setRecon] = useState([])
  const [reconDetailId, setReconDetailId] = useState(null)
  const pacingLoaded = useRef(false)
  const reconLoaded = useRef(false)

  const load = useCallback(() => {
    adsengineApi.metrics.dashboard()
      .then(r => setMetrics(r.data || {}))
      .catch(() => setMetrics({}))
    adsengineApi.alerts.list()
      .then(r => setAlerts(normalizeAlerts(r.data)))
      .catch(() => setAlerts([]))
  }, [])

  useEffect(() => { load() }, [load])

  // Drill-down : ouvre la liste des leads réels derrière un chiffre.
  const openDrill = (num) => {
    setDrill({ metric: num.metric, label: num.label })
    setLeadsLoading(true)
    setLeads([])
    adsengineApi.metrics.leads(num.metric)
      .then(r => setLeads(Array.isArray(r.data) ? r.data : (r.data?.results || r.data?.leads || [])))
      .catch(() => setLeads([]))
      .finally(() => setLeadsLoading(false))
  }
  const closeDrill = () => { setDrill(null); setLeads([]) }

  // Changement d'onglet — charge la donnée de l'onglet à la première ouverture.
  const switchTab = (next) => {
    setTab(next)
    if (next === 'pacing' && !pacingLoaded.current) {
      pacingLoaded.current = true
      adsengineApi.metrics.pacing()
        .then(r => setPacing(normalizePacing(r.data)))
        .catch(() => setPacing(normalizePacing(null)))
    }
    if (next === 'reconciliation' && !reconLoaded.current) {
      reconLoaded.current = true
      adsengineApi.reconciliation.list()
        .then(r => setRecon(normalizeReconciliation(r.data)))
        .catch(() => setRecon([]))
    }
  }

  return (
    <div className="page ae-dashboard">
      <div className="page-header">
        <h2>Tableau de bord publicitaire</h2>
      </div>

      {/* Bandeau d'alertes ENG13 (global, toutes vues) */}
      {alerts.length > 0 && (
        <div className="ae-alert-banner" data-testid="ae-alert-banner"
          style={{ display: 'grid', gap: '0.4rem', marginBottom: '1rem' }}>
          {alerts.map((a, i) => {
            const tone = alertTone(a.niveau)
            return (
              <div key={a.id ?? i} data-testid="ae-alert"
                style={{ display: 'flex', alignItems: 'center', gap: '0.5rem',
                  background: tone.bg, color: tone.color, padding: '0.5rem 0.75rem',
                  borderRadius: 8 }}>
                <Bell size={16} aria-hidden="true" />
                <span className="badge" style={{ background: 'rgba(255,255,255,0.6)', color: tone.color }}>
                  {tone.label}
                </span>
                <span>{a.message || a.titre}</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Onglets ENG42 */}
      <div className="ae-tabs" data-testid="ae-dashboard-tabs" role="group" aria-label="Vues du tableau de bord"
        style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1.25rem' }}>
        {TABS.map(t => (
          <button key={t.key} type="button"
            className={`btn ${tab === t.key ? 'btn-primary' : 'btn-light'}`}
            data-testid={`ae-tab-${t.key}`} aria-pressed={tab === t.key}
            onClick={() => switchTab(t.key)}>
            {t.label}
          </button>
        ))}
      </div>

      {/* ── Vue d'ensemble (inchangée) ── */}
      {tab === 'overview' && (
        <>
          {/* Chiffres cliquables (héro + tuiles) — chacun ouvre les leads réels */}
          <div style={{ display: 'grid', gap: '1rem',
            gridTemplateColumns: 'repeat(auto-fit, minmax(200px, 1fr))', marginBottom: '1.25rem' }}>
            {NUMBERS.map(num => (
              <button key={num.key} type="button"
                className={`card ae-number ${num.hero ? 'ae-hero' : `ae-tile ae-tile-${num.key}`}`}
                data-testid={num.hero ? 'ae-hero' : `ae-tile-${num.key}`}
                onClick={() => openDrill(num)}
                aria-label={`${num.label} — voir les leads`}
                style={{ textAlign: 'left', cursor: 'pointer',
                  gridColumn: num.hero ? '1 / -1' : 'auto',
                  padding: num.hero ? '1.5rem' : '1rem', border: '1px solid #e2e8f0' }}>
                <div style={{ color: '#64748b', fontSize: '0.85rem' }}>{num.label}</div>
                <div data-testid={`ae-value-${num.key}`}
                  style={{ fontSize: num.hero ? '2.4rem' : '1.5rem', fontWeight: 700 }}>
                  {fmtValue(num.fmt, metrics?.[num.key], metrics?.currency)}
                </div>
                <div style={{ color: '#2563eb', fontSize: '0.8rem', marginTop: '0.3rem' }}>
                  Voir les leads →
                </div>
              </button>
            ))}
          </div>

          {/* Panneau de drill-down : les leads réels derrière le chiffre */}
          {drill && (
            <section className="card ae-drill-panel" data-testid="ae-drill-panel"
              style={{ padding: '1rem' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <h3 style={{ margin: 0 }}>Leads derrière : {drill.label}</h3>
                <button type="button" className="btn btn-light" data-testid="ae-drill-close"
                  onClick={closeDrill}>Fermer</button>
              </div>
              {leadsLoading
                ? <p className="page-loading">Chargement…</p>
                : leads.length === 0
                  ? <p style={{ color: '#64748b' }} data-testid="ae-drill-empty">Aucun lead pour ce chiffre.</p>
                  : (
                    <table className="data-table" data-testid="ae-drill-table" style={{ marginTop: '0.5rem' }}>
                      <thead>
                        <tr><th>Lead</th><th>Ville</th><th>Étape</th><th>Devis</th><th /></tr>
                      </thead>
                      <tbody>
                        {leads.map((l, i) => (
                          <tr key={l.id ?? i} data-testid="ae-drill-lead">
                            <td>{l.nom || l.name || '—'}</td>
                            <td>{l.ville || l.city || '—'}</td>
                            <td>{l.stage_label || l.etape || '—'}</td>
                            <td>{l.devis_ref || '—'}{l.montant != null ? ` (${formatMAD(l.montant)})` : ''}</td>
                            <td>
                              {l.id != null && (
                                <Link to={`/crm/leads/${l.id}`} className="btn btn-light"
                                  data-testid="ae-drill-lead-link"
                                  style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                  <ExternalLink size={14} aria-hidden="true" /> Ouvrir
                                </Link>
                              )}
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
            </section>
          )}
        </>
      )}

      {/* ── Pacing (ENG20/ENG42) ── */}
      {tab === 'pacing' && (
        <section className="ae-pacing" data-testid="ae-pacing">
          {!pacing
            ? <p className="page-loading">Chargement…</p>
            : (
              <>
                <div style={{ display: 'grid', gap: '1rem',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', marginBottom: '1rem' }}>
                  <div className="card" data-testid="ae-pacing-enveloppe" style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Enveloppe du mois</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-enveloppe-val">
                      {formatMAD(pacing.enveloppe_mad)}</div>
                  </div>
                  {/* Burn : cliquable vers le détail des dépenses */}
                  <button type="button" className="card ae-pacing-burn" data-testid="ae-pacing-burn"
                    onClick={() => setPacingDetailOpen(o => !o)}
                    aria-label="Dépense engagée — voir le détail"
                    style={{ textAlign: 'left', cursor: 'pointer', padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Dépense engagée (burn)</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-burn-val">
                      {formatMAD(pacing.depense_mad)}</div>
                    <div style={{ color: '#2563eb', fontSize: '0.8rem', marginTop: '0.3rem' }}>Voir le détail →</div>
                  </button>
                  <div className="card" data-testid="ae-pacing-projection" style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Projection fin de mois</div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-projection-val">
                      {formatMAD(pacing.projection_mad)}</div>
                    {pacing.jours_restants != null && (
                      <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.3rem' }}>
                        {formatRatio(pacing.jours_restants, 0)} jour(s) restant(s)</div>
                    )}
                  </div>
                  <div className="card" data-testid="ae-pacing-etat" style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>État</div>
                    <span className="badge" data-testid="ae-pacing-etat-val"
                      style={{ ...(() => { const t = pacingStateTone(pacing.etat); return { background: t.bg, color: t.color } })(),
                        fontSize: '1rem', marginTop: '0.3rem', display: 'inline-block' }}>
                      {pacing.etat_display}</span>
                  </div>
                </div>

                {/* Détail des dépenses (drill) */}
                {pacingDetailOpen && (
                  <section className="card ae-pacing-detail" data-testid="ae-pacing-detail" style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ margin: 0 }}>Détail des dépenses</h3>
                      <button type="button" className="btn btn-light" data-testid="ae-pacing-detail-close"
                        onClick={() => setPacingDetailOpen(false)}>Fermer</button>
                    </div>
                    {pacing.lignes.length === 0
                      ? <p style={{ color: '#64748b' }} data-testid="ae-pacing-detail-empty">Aucun détail disponible.</p>
                      : (
                        <table className="data-table" style={{ marginTop: '0.5rem' }}>
                          <thead><tr><th>Poste</th><th>Montant</th></tr></thead>
                          <tbody>
                            {pacing.lignes.map(l => (
                              <tr key={l.id} data-testid="ae-pacing-detail-row">
                                <td>{l.label}</td><td>{formatMAD(l.montant_mad)}</td>
                              </tr>
                            ))}
                          </tbody>
                        </table>
                      )}
                  </section>
                )}
              </>
            )}
        </section>
      )}

      {/* ── Réconciliation Meta-vs-ERP (ENG31/ENG42) ── */}
      {tab === 'reconciliation' && (
        <section className="ae-recon" data-testid="ae-recon">
          {recon.length === 0
            ? <p data-testid="ae-recon-empty" style={{ color: '#64748b' }}>
                Aucune ligne de réconciliation.</p>
            : (
              <table className="data-table" data-testid="ae-recon-table">
                <thead>
                  <tr><th>Campagne</th><th>Meta</th><th>ERP</th><th>Écart</th><th>Statut</th><th /></tr>
                </thead>
                <tbody>
                  {recon.map(r => {
                    const tone = reconStatusTone(r.statut)
                    return (
                      <tr key={r.id} data-testid="ae-recon-row">
                        <td>{r.campagne}</td>
                        <td>{formatMAD(r.meta_mad)}</td>
                        <td>{formatMAD(r.erp_mad)}</td>
                        <td data-testid={`ae-recon-ecart-${r.id}`}>
                          {formatMAD(r.ecart_mad)}
                          {r.ecart_pct != null ? ` (${formatPercent(r.ecart_pct)})` : ''}
                        </td>
                        <td>
                          <span className="badge" style={{ background: tone.bg, color: tone.color }}>
                            {r.statut_display}</span>
                        </td>
                        <td>
                          <button type="button" className="btn btn-light" data-testid={`ae-recon-open-${r.id}`}
                            onClick={() => setReconDetailId(id => id === r.id ? null : r.id)}>
                            Détail</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            )}

          {/* Détail d'une ligne de réconciliation (Meta vs ERP, poste par poste) */}
          {reconDetailId != null && (() => {
            const row = recon.find(r => r.id === reconDetailId)
            if (!row) return null
            return (
              <section className="card ae-recon-detail" data-testid="ae-recon-detail"
                style={{ padding: '1rem', marginTop: '1rem' }}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <h3 style={{ margin: 0 }}>Détail — {row.campagne}</h3>
                  <button type="button" className="btn btn-light" data-testid="ae-recon-detail-close"
                    onClick={() => setReconDetailId(null)}>Fermer</button>
                </div>
                {row.lignes.length === 0
                  ? <p style={{ color: '#64748b' }} data-testid="ae-recon-detail-empty">Aucun détail disponible.</p>
                  : (
                    <table className="data-table" style={{ marginTop: '0.5rem' }}>
                      <thead><tr><th>Poste</th><th>Meta</th><th>ERP</th></tr></thead>
                      <tbody>
                        {row.lignes.map(l => (
                          <tr key={l.id} data-testid="ae-recon-detail-row">
                            <td>{l.label}</td><td>{formatMAD(l.meta_mad)}</td><td>{formatMAD(l.erp_mad)}</td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  )}
              </section>
            )
          })()}
        </section>
      )}
    </div>
  )
}
