import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { Bell, ExternalLink } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMAD, formatRatio, normalizeAlerts, alertTone } from './adsengine'

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
   ========================================================================== */

// Définition des chiffres cliquables. `metric` = clé passée à metrics.leads().
// `fmt` = 'mad' (montant) | 'ratio' (décimal). Le héro est marqué `hero`.
const NUMBERS = [
  { key: 'cost_per_signature', metric: 'signature', label: 'Coût par signature', fmt: 'mad', hero: true },
  { key: 'spend', metric: 'spend', label: 'Dépense', fmt: 'mad' },
  { key: 'cpl', metric: 'lead', label: 'Coût par lead', fmt: 'mad' },
  { key: 'frequency', metric: 'frequency', label: 'Fréquence', fmt: 'ratio' },
]

function fmtValue(fmt, value) {
  return fmt === 'ratio' ? formatRatio(value) : formatMAD(value)
}

export default function DashboardScreen() {
  const [metrics, setMetrics] = useState(null)
  const [alerts, setAlerts] = useState([])
  const [drill, setDrill] = useState(null) // { metric, label }
  const [leads, setLeads] = useState([])
  const [leadsLoading, setLeadsLoading] = useState(false)

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

  return (
    <div className="page ae-dashboard">
      <div className="page-header">
        <h2>Tableau de bord publicitaire</h2>
      </div>

      {/* Bandeau d'alertes ENG13 */}
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
              {fmtValue(num.fmt, metrics?.[num.key])}
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
    </div>
  )
}
