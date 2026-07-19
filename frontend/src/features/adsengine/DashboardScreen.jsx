import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Bell, ExternalLink, Printer, Download } from 'lucide-react'
import adsengineApi from './adsengineApi'
import AlertCenter from './AlertCenter'
import CommandPalette from './CommandPalette'
import MetricHelp from './MetricHelp'
import {
  formatMAD, formatMoney, formatNumber, formatRatio, formatPercent,
  normalizeAlerts, alertTone, normalizePacing, pacingStateTone,
  normalizeReconciliation, reconStatusTone,
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

   ADSDEEP61 — « Dashboard v2 » : deux tuiles ADDITIVES sous la grille héro de
   la vue d'ensemble (aucun nouvel onglet) — conversations WhatsApp RÉELLES
   (CTWA) et MER mixte. Le MER montre la dépense Meta (devise du COMPTE) et le
   CA signé Odoo (MAD) CÔTE À CÔTE : ce sont deux devises différentes, JAMAIS
   converties/fusionnées en un seul chiffre côté front — le ratio n'est affiché
   QUE si l'API le renvoie déjà (elle ne le calcule elle-même que si les deux
   montants partagent la même devise). Chaque tuile porte une sparkline 14 j
   (``metrics.dashboardV2``, endpoint optionnel — absent en test unitaire des
   autres écrans, d'où le garde `?.`).
   ========================================================================== */

// ADSDEEP61 — mini sparkline SVG (pure, sans dépendance de charting) pour les
// tuiles du Dashboard v2. ``points`` = [{date, value}], jamais vide ici (le
// backend renvoie toujours 14 points, un jour sans donnée valant 0).
function Sparkline({ points, testId, label }) {
  if (!points || points.length === 0) return null
  const values = points.map(p => Number(p.value) || 0)
  const max = Math.max(...values, 0)
  const min = Math.min(...values, 0)
  const range = (max - min) || 1
  const w = 100
  const h = 28
  const step = points.length > 1 ? w / (points.length - 1) : 0
  const coords = points.map((p, i) => {
    const x = i * step
    const y = h - ((values[i] - min) / range) * h
    return `${x},${Number.isFinite(y) ? y : h}`
  }).join(' ')
  return (
    <svg data-testid={testId} role="img" width="100%" height="28" viewBox={`0 0 ${w} ${h}`}
      preserveAspectRatio="none" style={{ display: 'block', marginTop: '0.4rem' }}
      aria-label={label || `Évolution sur ${points.length} jours`}>
      <polyline points={coords} fill="none" stroke="#2563eb" strokeWidth="2" />
    </svg>
  )
}

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
  { key: 'signaux', label: 'Signaux' },
]

/* ============================================================================
   SIG4 — Console de signaux (dd-assumption-engine.md §11).
   ----------------------------------------------------------------------------
   Ta structure 3 couches (créatif / opérations / garde-fous durs) = ce que
   fait l'industrie : le composite reste HORS de l'optimiseur (affichage +
   alerte seulement, jamais un poids appris à notre volume). Deux scores de
   santé DISTINCTS (SIG1, poids fixes en config) pour qu'une vente lente ne
   salisse jamais l'allocation créative ; le quadrant de garde-fous DURS (SIG2 :
   fréquence/quality_ranking/CPL/qualité de compte) NE FAIT QUE freiner ; le
   drill-down (SIG3) montre le filigrane de cohorte (proxy 7j → CPL 14-28j →
   signature 60-90j). Helpers tenus LOCAUX à cet écran (adsengine.js est hors
   périmètre de la lane frontend/adsengine SIG4) — aucun score n'est recalculé,
   uniquement lu depuis l'API.
   ========================================================================== */
function bandTone(bande) {
  const b = String(bande || '').toLowerCase()
  if (b.includes('rouge') || b.includes('critique')) return { bg: '#fee2e2', color: '#991b1b' }
  if (b.includes('orange') || b.includes('alerte')) return { bg: '#fef9c3', color: '#854d0e' }
  if (b.includes('vert') || b.includes('ok')) return { bg: '#dcfce7', color: '#166534' }
  return { bg: '#f1f5f9', color: '#475569' }
}

function normalizeHealthScore(raw) {
  const o = raw && typeof raw === 'object' ? raw : {}
  return {
    score: Number.isFinite(Number(o.score)) ? Number(o.score) : null,
    bande: o.bande || o.band || '',
    bande_display: o.bande_display || o.band_display || o.bande || '—',
  }
}

function normalizeSignals(raw) {
  const s = raw && typeof raw === 'object' ? raw : {}
  const guardrailsRaw = Array.isArray(s.guardrails) ? s.guardrails
    : (Array.isArray(s.garde_fous) ? s.garde_fous : [])
  return {
    creatif: normalizeHealthScore(s.creatif || s.creative),
    operations: normalizeHealthScore(s.operations || s.ops),
    guardrails: guardrailsRaw.filter(Boolean).map((g, i) => ({
      key: g.key ?? i,
      label: g.label || g.nom || `Garde-fou ${i + 1}`,
      valeur: Number.isFinite(Number(g.valeur ?? g.value)) ? Number(g.valeur ?? g.value) : null,
      seuil: Number.isFinite(Number(g.seuil ?? g.threshold)) ? Number(g.seuil ?? g.threshold) : null,
      freine: !!(g.freine ?? g.blocking),
      statut_display: g.statut_display || (g.freine ?? g.blocking ? 'Freine' : 'OK'),
    })),
  }
}

function normalizeCohorts(raw) {
  const list = Array.isArray(raw) ? raw : (raw?.results || raw?.cohortes || [])
  return (list || []).filter(Boolean).map((c, i) => ({
    id: c.id ?? i,
    fenetre: c.fenetre || c.window || `Cohorte ${i + 1}`,
    valeur: Number.isFinite(Number(c.valeur ?? c.value)) ? Number(c.valeur ?? c.value) : null,
    maturite_display: c.maturite_display || c.maturity_display || '',
  }))
}

const SIGNAL_CARDS = [
  { key: 'creatif', label: 'Santé créative' },
  { key: 'operations', label: 'Santé opérations' },
]
// PUB54 — clé MetricHelp par carte de signal.
const SIGNAL_METRIC_HELP_KEY = { creatif: 'sante_creative', operations: 'sante_operations' }

export default function DashboardScreen() {
  const [metrics, setMetrics] = useState(null)
  // ADSDEEP61 — tuiles Dashboard v2 (conversations + MER mixte), optionnelles.
  const [v2, setV2] = useState(null)
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
  // PUB47 — export CSV SERVEUR (ReportExportView, jusqu'ici sans consommateur
  // front) pour la table de réconciliation — aucun export n'existait ici.
  const [reconExportBusy, setReconExportBusy] = useState(false)
  const [reconExportErr, setReconExportErr] = useState(false)

  // SIG4 — console de signaux (chargée paresseusement, comme pacing/recon).
  const [signals, setSignals] = useState(null)
  const [signalDrill, setSignalDrill] = useState(null) // { key, label }
  const [cohorts, setCohorts] = useState([])
  const [cohortsLoading, setCohortsLoading] = useState(false)
  const signalsLoaded = useRef(false)

  const load = useCallback(() => {
    adsengineApi.metrics.dashboard()
      .then(r => setMetrics(r.data || {}))
      .catch(() => setMetrics({}))
    adsengineApi.alerts.list()
      .then(r => setAlerts(normalizeAlerts(r.data)))
      .catch(() => setAlerts([]))
    // ADSDEEP61 — Dashboard v2 (endpoint optionnel : garde `?.` pour ne pas
    // casser les écrans/tests qui mockent une API `metrics` réduite).
    const dashboardV2Fn = adsengineApi.metrics?.dashboardV2
    if (dashboardV2Fn) {
      dashboardV2Fn()
        .then(r => setV2(r.data || null))
        .catch(() => setV2(null))
    }
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
    if (next === 'signaux' && !signalsLoaded.current) {
      signalsLoaded.current = true
      adsengineApi.signals.get()
        .then(r => setSignals(normalizeSignals(r.data)))
        .catch(() => setSignals(normalizeSignals(null)))
    }
  }

  // PUB47 — télécharge le CSV serveur de réconciliation (blob, jamais un
  // ``data:`` URI fabriqué côté client — source de vérité unique, PUB12).
  const exportReconciliationCsv = async () => {
    setReconExportBusy(true); setReconExportErr(false)
    try {
      const r = await adsengineApi.reports.export({ table: 'reconciliation' })
      const url = window.URL.createObjectURL(new Blob([r.data]))
      const a = document.createElement('a')
      a.href = url
      a.download = 'reconciliation-taqinor.csv'
      a.click()
      window.URL.revokeObjectURL(url)
    } catch {
      setReconExportErr(true)
    } finally {
      setReconExportBusy(false)
    }
  }

  // SIG3 — drill-down par signal/cohorte (filigrane de maturation).
  const openSignalDrill = (key, label) => {
    setSignalDrill({ key, label })
    setCohortsLoading(true)
    setCohorts([])
    adsengineApi.signals.cohort({ signal: key })
      .then(r => setCohorts(normalizeCohorts(r.data)))
      .catch(() => setCohorts([]))
      .finally(() => setCohortsLoading(false))
  }
  const closeSignalDrill = () => { setSignalDrill(null); setCohorts([]) }

  return (
    <div className="page ae-dashboard ae-print-area">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2>Tableau de bord publicitaire</h2>
        {/* PUB47 — impression navigateur (feuille globale print.css, VX80 :
            chrome masqué, noir-sur-blanc, tables complètes) : distinct des PDF
            WeasyPrint client (règle #4), zéro dépendance nouvelle. */}
        <div className="no-print" style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button type="button" className="btn btn-light" data-testid="ae-dashboard-print"
            onClick={() => window.print()}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
            <Printer size={15} aria-hidden="true" /> Imprimer / PDF
          </button>
          {/* PUB48 — centre de notifications persistant de la console */}
          <AlertCenter />
          {/* PUB51 — palette de commandes (Ctrl-K) */}
          <CommandPalette />
        </div>
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
              // PUB54 — le « ? » d'aide vit HORS du bouton (jamais un bouton
              // imbriqué dans un bouton) : la tuile-héro/bouton reste
              // inchangée (mêmes hooks ae-*), le « ? » est un frère positionné
              // en coin.
              <div key={num.key} style={{ position: 'relative',
                gridColumn: num.hero ? '1 / -1' : 'auto' }}>
                <button type="button"
                  className={`card ae-number ${num.hero ? 'ae-hero' : `ae-tile ae-tile-${num.key}`}`}
                  data-testid={num.hero ? 'ae-hero' : `ae-tile-${num.key}`}
                  onClick={() => openDrill(num)}
                  aria-label={`${num.label} — voir les leads`}
                  style={{ textAlign: 'left', cursor: 'pointer', width: '100%',
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
                <div style={{ position: 'absolute', top: num.hero ? '1.1rem' : '0.7rem', right: '0.7rem' }}>
                  <MetricHelp metric={num.key} label={num.label} />
                </div>
              </div>
            ))}
          </div>

          {/* ADSDEEP61 — Dashboard v2 : conversations réelles + MER mixte */}
          {v2 && (
            <section className="ae-dashboard-v2" data-testid="ae-dv2" style={{ marginBottom: '1.25rem' }}>
              <div style={{ display: 'grid', gap: '1rem',
                gridTemplateColumns: 'repeat(auto-fit, minmax(240px, 1fr))' }}>
                <div className="card" data-testid="ae-dv2-conversations"
                  style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                    Conversations WhatsApp ({v2.window_days} j)
                  </div>
                  <div data-testid="ae-dv2-conversations-total" style={{ fontSize: '1.6rem', fontWeight: 700 }}>
                    {formatNumber(v2.conversations?.total)}
                  </div>
                  <Sparkline points={v2.conversations?.sparkline} testId="ae-dv2-conversations-sparkline"
                    label={`Conversations par jour sur ${v2.window_days} jours`} />
                </div>

                <div className="card" data-testid="ae-dv2-mer"
                  style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                  <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                    MER mixte ({v2.window_days} j)
                    <MetricHelp metric="mer" label="MER mixte" />
                  </div>
                  <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.2rem 0.6rem',
                    margin: '0.35rem 0 0', fontSize: '1.05rem' }}>
                    <dt style={{ color: '#64748b', fontWeight: 400 }}>Dépense Meta</dt>
                    <dd style={{ margin: 0, fontWeight: 700 }} data-testid="ae-dv2-mer-spend">
                      {formatMoney(v2.mer?.spend, v2.mer?.spend_currency)}
                    </dd>
                    <dt style={{ color: '#64748b', fontWeight: 400 }}>CA signé (Odoo)</dt>
                    <dd style={{ margin: 0, fontWeight: 700 }} data-testid="ae-dv2-mer-ca">
                      {formatMoney(v2.mer?.signed_ca_mad, v2.mer?.signed_ca_currency || 'MAD')}
                    </dd>
                  </dl>
                  {/* Le ratio n'est affiché QUE si l'API le fournit déjà (même
                      devise) — jamais recalculé/converti côté front. */}
                  {v2.mer?.mer_ratio != null && (
                    <div data-testid="ae-dv2-mer-ratio" style={{ fontSize: '0.85rem', marginTop: '0.2rem' }}>
                      MER : {formatRatio(v2.mer.mer_ratio)}
                    </div>
                  )}
                  <p data-testid="ae-dv2-mer-note" style={{ fontSize: '0.75rem', color: '#94a3b8', margin: '0.4rem 0 0' }}>
                    {v2.mer?.note}
                  </p>
                  <div style={{ display: 'flex', gap: '0.75rem' }}>
                    <div style={{ flex: 1 }}>
                      <Sparkline points={v2.mer?.spend_sparkline} testId="ae-dv2-mer-spend-sparkline"
                        label={`Dépense Meta par jour sur ${v2.window_days} jours`} />
                    </div>
                    <div style={{ flex: 1 }}>
                      <Sparkline points={v2.mer?.signed_ca_sparkline} testId="ae-dv2-mer-ca-sparkline"
                        label={`CA signé Odoo par jour sur ${v2.window_days} jours`} />
                    </div>
                  </div>
                </div>
              </div>
            </section>
          )}

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
                            <td data-label="Lead">{l.nom || l.name || '—'}</td>
                            <td data-label="Ville">{l.ville || l.city || '—'}</td>
                            <td data-label="Étape">{l.stage_label || l.etape || '—'}</td>
                            <td data-label="Devis">{l.devis_ref || '—'}{l.montant != null ? ` (${formatMAD(l.montant)})` : ''}</td>
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
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                      Enveloppe du mois
                      <MetricHelp metric="pacing_enveloppe" label="Enveloppe du mois" />
                    </div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-enveloppe-val">
                      {formatMAD(pacing.enveloppe_mad)}</div>
                  </div>
                  {/* Burn : cliquable vers le détail des dépenses. Le « ? »
                      vit HORS du bouton (jamais un bouton dans un bouton). */}
                  <div style={{ position: 'relative' }}>
                    <button type="button" className="card ae-pacing-burn" data-testid="ae-pacing-burn"
                      onClick={() => setPacingDetailOpen(o => !o)}
                      aria-label="Dépense engagée — voir le détail"
                      style={{ textAlign: 'left', cursor: 'pointer', width: '100%', padding: '1rem', border: '1px solid #e2e8f0' }}>
                      <div style={{ color: '#64748b', fontSize: '0.85rem' }}>Dépense engagée (burn)</div>
                      <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-burn-val">
                        {formatMAD(pacing.depense_mad)}</div>
                      <div style={{ color: '#2563eb', fontSize: '0.8rem', marginTop: '0.3rem' }}>Voir le détail →</div>
                    </button>
                    <div style={{ position: 'absolute', top: '0.7rem', right: '0.7rem' }}>
                      <MetricHelp metric="pacing_burn" label="Dépense engagée (burn)" />
                    </div>
                  </div>
                  <div className="card" data-testid="ae-pacing-projection" style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                      Projection fin de mois
                      <MetricHelp metric="pacing_projection" label="Projection fin de mois" />
                    </div>
                    <div style={{ fontSize: '1.4rem', fontWeight: 700 }} data-testid="ae-pacing-projection-val">
                      {formatMAD(pacing.projection_mad)}</div>
                    {pacing.jours_restants != null && (
                      <div style={{ color: '#64748b', fontSize: '0.8rem', marginTop: '0.3rem' }}>
                        {formatRatio(pacing.jours_restants, 0)} jour(s) restant(s)</div>
                    )}
                  </div>
                  <div className="card" data-testid="ae-pacing-etat" style={{ padding: '1rem', border: '1px solid #e2e8f0' }}>
                    <div style={{ color: '#64748b', fontSize: '0.85rem' }}>
                      État
                      <MetricHelp metric="pacing_etat" label="État du rythme" />
                    </div>
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
                                <td data-label="Poste">{l.label}</td>
                                <td data-label="Montant">{formatMAD(l.montant_mad)}</td>
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
          <p style={{ color: '#64748b', fontSize: '0.85rem', margin: '0 0 0.75rem' }}>
            Réconciliation Meta ↔ ERP
            <MetricHelp metric="reconciliation" label="Réconciliation Meta ↔ ERP" />
          </p>
          {recon.length === 0
            ? <p data-testid="ae-recon-empty" style={{ color: '#64748b' }}>
                Aucune ligne de réconciliation.</p>
            : (
              <>
                {/* PUB47 — CSV serveur (aucun export n'existait sur cette table) */}
                <div className="no-print" style={{ display: 'flex', justifyContent: 'flex-end', marginBottom: '0.5rem' }}>
                  <button type="button" className="btn btn-light" data-testid="ae-recon-export"
                    disabled={reconExportBusy} onClick={exportReconciliationCsv}
                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                    <Download size={14} aria-hidden="true" /> Exporter en CSV
                  </button>
                </div>
                {reconExportErr && (
                  <p data-testid="ae-recon-export-err" style={{ color: '#dc2626' }}>Export impossible.</p>
                )}
              <table className="data-table" data-testid="ae-recon-table">
                <thead>
                  <tr><th>Campagne</th><th>Meta</th><th>ERP</th><th>Écart</th><th>Statut</th><th /></tr>
                </thead>
                <tbody>
                  {recon.map(r => {
                    const tone = reconStatusTone(r.statut)
                    return (
                      <tr key={r.id} data-testid="ae-recon-row">
                        <td data-label="Campagne">{r.campagne}</td>
                        <td data-label="Meta">{formatMAD(r.meta_mad)}</td>
                        <td data-label="ERP">{formatMAD(r.erp_mad)}</td>
                        <td data-label="Écart" data-testid={`ae-recon-ecart-${r.id}`}>
                          {formatMAD(r.ecart_mad)}
                          {r.ecart_pct != null ? ` (${formatPercent(r.ecart_pct)})` : ''}
                        </td>
                        <td data-label="Statut">
                          <span className="badge" style={{ background: tone.bg, color: tone.color }}>
                            {r.statut_display}</span>
                        </td>
                        <td>
                          <button type="button" className="btn btn-light" data-testid={`ae-recon-open-${r.id}`}
                            onClick={() => setReconDetailId(id => id === r.id ? null : r.id)}
                            style={{ minHeight: 44, minWidth: 44 }}>
                            Détail</button>
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
              </>
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
                            <td data-label="Poste">{l.label}</td>
                            <td data-label="Meta">{formatMAD(l.meta_mad)}</td>
                            <td data-label="ERP">{formatMAD(l.erp_mad)}</td>
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

      {/* ── Signaux (SIG1-4) ── */}
      {tab === 'signaux' && (
        <section className="ae-signals" data-testid="ae-signals">
          {!signals
            ? <p className="page-loading">Chargement…</p>
            : (
              <>
                {/* SIG1 — deux scores de santé DISTINCTS (poids fixes, hors optimiseur) */}
                <div style={{ display: 'grid', gap: '1rem',
                  gridTemplateColumns: 'repeat(auto-fit, minmax(220px, 1fr))', marginBottom: '1.25rem' }}>
                  {SIGNAL_CARDS.map(sc => {
                    const data = signals[sc.key]
                    const tone = bandTone(data.bande)
                    // PUB54 — le « ? » vit HORS du bouton (jamais imbriqué).
                    return (
                      <div key={sc.key} style={{ position: 'relative' }}>
                        <button type="button" className="card ae-signal-score"
                          data-testid={`ae-signal-${sc.key}`}
                          onClick={() => openSignalDrill(sc.key, sc.label)}
                          aria-label={`${sc.label} — voir le détail par cohorte`}
                          style={{ textAlign: 'left', cursor: 'pointer', width: '100%', padding: '1rem', border: '1px solid #e2e8f0' }}>
                          <div style={{ color: '#64748b', fontSize: '0.85rem' }}>{sc.label}</div>
                          <div data-testid={`ae-signal-${sc.key}-score`} style={{ fontSize: '1.6rem', fontWeight: 700 }}>
                            {formatRatio(data.score)}
                          </div>
                          <span className="badge" data-testid={`ae-signal-${sc.key}-bande`}
                            style={{ background: tone.bg, color: tone.color }}>
                            {data.bande_display}
                          </span>
                        </button>
                        <div style={{ position: 'absolute', top: '0.7rem', right: '0.7rem' }}>
                          <MetricHelp metric={SIGNAL_METRIC_HELP_KEY[sc.key]} label={sc.label} />
                        </div>
                      </div>
                    )
                  })}
                </div>

                {/* SIG2 — quadrant de garde-fous DURS (ne fait QUE freiner) */}
                <h3 style={{ margin: '0 0 0.6rem' }}>
                  Quadrant de garde-fous durs
                  <MetricHelp metric="guardrail_quadrant" label="Quadrant de garde-fous durs" />
                </h3>
                {signals.guardrails.length === 0
                  ? <p data-testid="ae-guardrail-empty" style={{ color: '#64748b' }}>Aucun garde-fou.</p>
                  : (
                    <div data-testid="ae-guardrail-quadrant" style={{ display: 'grid', gap: '0.75rem',
                      gridTemplateColumns: 'repeat(2, 1fr)', marginBottom: '1.25rem' }}>
                      {signals.guardrails.map(g => (
                        <div key={g.key} className="card" data-testid={`ae-guardrail-${g.key}`}
                          style={{ padding: '0.75rem', border: `1px solid ${g.freine ? '#dc2626' : '#e2e8f0'}` }}>
                          <div style={{ color: '#64748b', fontSize: '0.8rem' }}>{g.label}</div>
                          <div style={{ fontWeight: 700 }}>
                            {formatRatio(g.valeur)}{g.seuil != null ? ` / ${formatRatio(g.seuil)}` : ''}
                          </div>
                          <span className="badge" data-testid={`ae-guardrail-statut-${g.key}`}
                            style={{ background: g.freine ? '#fee2e2' : '#dcfce7',
                              color: g.freine ? '#991b1b' : '#166534' }}>
                            {g.statut_display}
                          </span>
                        </div>
                      ))}
                    </div>
                  )}

                {/* SIG3 — drill-down par signal/cohorte (filigrane de maturation) */}
                {signalDrill && (
                  <section className="card ae-signal-drill" data-testid="ae-signal-drill" style={{ padding: '1rem' }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                      <h3 style={{ margin: 0 }}>Détail par cohorte — {signalDrill.label}</h3>
                      <button type="button" className="btn btn-light" data-testid="ae-signal-drill-close"
                        onClick={closeSignalDrill}>Fermer</button>
                    </div>
                    {cohortsLoading
                      ? <p className="page-loading">Chargement…</p>
                      : cohorts.length === 0
                        ? <p style={{ color: '#64748b' }} data-testid="ae-signal-drill-empty">
                            Aucune cohorte pour ce signal.</p>
                        : (
                          <table className="data-table" data-testid="ae-signal-drill-table" style={{ marginTop: '0.5rem' }}>
                            <thead><tr><th>Fenêtre</th><th>Valeur</th><th>Maturité</th></tr></thead>
                            <tbody>
                              {cohorts.map(c => (
                                <tr key={c.id} data-testid="ae-signal-drill-row">
                                  <td data-label="Fenêtre">{c.fenetre}</td>
                                  <td data-label="Valeur">{formatRatio(c.valeur)}</td>
                                  <td data-label="Maturité">{c.maturite_display}</td>
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
    </div>
  )
}
