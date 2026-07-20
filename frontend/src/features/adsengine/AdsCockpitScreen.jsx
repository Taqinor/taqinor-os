import { useEffect, useState, useCallback, useMemo, useRef } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Video, ImageOff, FileText } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMAD, formatMoney, formatNumber, formatPercent, formatRatio, sortCockpitRows } from './adsengine'
import DataWindowNotice from './DataWindowNotice'
import AdCreativePanel from './AdCreativePanel'
import ManualActionMenu from './ManualActionMenu'
// PUB3 — panneau démographie/placement/région/heure, construit+testé mais
// jamais monté nulle part avant cette tâche (breakdowns/ est synchronisé
// chaque semaine côté back mais restait invisible).
import BreakdownsPanel from './BreakdownsPanel'
import DateRangeBar from './DateRangeBar'
import { presetRange, previousRange, computeDelta, formatDeltaPct } from './dateRange'
import SyncStatusBanner from './SyncStatusBanner'
// FIXPUB4 — bandeau « version périmée » (réutilise le SW existant).
import UpdateBanner from './UpdateBanner'
import { COCKPIT_VIEWS, applyCockpitView, loadSavedCockpitView, saveCockpitView } from './cockpitViews'

// PUB40 — dépense totale visible (somme ``depense_mad`` des lignes) — pure,
// testable isolément ; une ligne sans dépense compte pour 0 (jamais NaN).
function totalSpend(rows) {
  return (rows || []).reduce((sum, r) => sum + (Number(r.depense_mad) || 0), 0)
}

/* ============================================================================
   ADSDEEP22 — Cockpit par ad (écran-console QUOTIDIEN du fondateur).
   ----------------------------------------------------------------------------
   Une ligne PAR AD : miniature créatif, dépense, conversations, leads réels,
   CPL, signatures, coût/signature, fréquence, badge de fatigue (ADSDEEP45) et
   statut + apprentissage (badge hérité de l'ad set parent, ADSDEEP32). Table
   TRIABLE sur chaque colonne chiffrée (`sortCockpitRows`, adsengine.js — pur,
   valeurs manquantes toujours reléguées en fin de tri). Un clic sur une ligne
   DESCEND jusqu'au détail créatif de l'ad (réutilise `AdCreativePanel`,
   ADSDEEP14 — aucune réécriture).
   Toutes les valeurs viennent de ``metrics.adsCockpit`` — rien n'est inventé.
   ========================================================================== */

// DATAPUB5 — parité colonnes Ads Manager : source UNIQUE (en-tête + cellule) de
// TOUTES les métriques détenues. `render(row, currency)` produit la cellule ; le
// sélecteur de colonnes (persisté localStorage) choisit lesquelles afficher.
// Toutes sont triables (sortCockpitRows est null-safe et coerce les nombres).
const ALL_COLUMNS = [
  { key: 'nom', label: 'Ad', render: (r) => r.nom || '—' },
  { key: 'statut_display', label: 'Statut / apprentissage', render: (r) => (
    <>{r.statut_display || '—'}{' '}
      <span className="badge" data-testid="ae-cockpit-learning-badge">
        {r.learning_badge?.label || 'Inconnu'}</span></>
  ) },
  { key: 'depense_mad', label: 'Dépense', render: (r, c) => formatMoney(r.depense_mad, c) },
  { key: 'impressions', label: 'Impressions', render: (r) => formatNumber(r.impressions) },
  { key: 'reach', label: 'Couverture', render: (r) => formatNumber(r.reach) },
  { key: 'clics', label: 'Clics', render: (r) => formatNumber(r.clics) },
  { key: 'clics_lien', label: 'Clics sur lien', render: (r) => formatNumber(r.clics_lien) },
  { key: 'ctr', label: 'CTR', render: (r) => formatPercent(r.ctr, 2) },
  { key: 'cpc_mad', label: 'CPC', render: (r, c) => r.cpc_mad == null ? '—' : formatMoney(r.cpc_mad, c) },
  { key: 'cpm_mad', label: 'CPM', render: (r, c) => r.cpm_mad == null ? '—' : formatMoney(r.cpm_mad, c) },
  { key: 'conversations', label: 'Conversations', render: (r) => formatNumber(r.conversations) },
  { key: 'resultats', label: 'Résultats', render: (r) => formatNumber(r.resultats) },
  { key: 'nb_leads', label: 'Leads', render: (r) => formatNumber(r.nb_leads) },
  // FIXPUB9 — compte RÉEL Odoo/CRM, à côté du compte Meta (nb_leads).
  { key: 'leads_odoo', label: 'Leads (Odoo)', render: (r) => formatNumber(r.leads_odoo) },
  { key: 'cpl_mad', label: 'CPL', render: (r, c) => r.cpl_mad == null ? '—' : formatMoney(r.cpl_mad, c) },
  // CPL sur les leads Odoo (numérateur = dépense en devise du COMPTE).
  { key: 'cpl_odoo', label: 'CPL (Odoo)', render: (r) => r.cpl_odoo == null ? '—' : formatMAD(r.cpl_odoo) },
  { key: 'signatures', label: 'Signatures', render: (r) => formatNumber(r.signatures) },
  { key: 'cost_per_signature_mad', label: 'Coût / signature', render: (r, c) => r.cost_per_signature_mad == null ? '—' : formatMoney(r.cost_per_signature_mad, c) },
  { key: 'frequency', label: 'Fréquence', render: (r) => r.frequency == null ? '—' : formatRatio(r.frequency) },
  { key: 'hook_rate', label: 'Hook rate', render: (r) => formatPercent(r.hook_rate, 1) },
  { key: 'hold_rate', label: 'Hold rate', render: (r) => formatPercent(r.hold_rate, 1) },
]

// Colonnes visibles par défaut = le jeu historique (comportement inchangé tant
// que le fondateur n'ajoute pas de colonne). Les autres sont opt-in via le
// sélecteur (parité complète Ads Manager à la demande).
const DEFAULT_COLUMN_KEYS = [
  'nom', 'statut_display', 'depense_mad', 'conversations', 'nb_leads',
  'leads_odoo', 'cpl_mad', 'cpl_odoo', 'signatures',
  'cost_per_signature_mad', 'frequency',
]

const COLUMN_STORAGE_KEY = 'ae-cockpit-columns'

function loadSavedColumns() {
  try {
    const raw = window.localStorage.getItem(COLUMN_STORAGE_KEY)
    if (!raw) return null
    const arr = JSON.parse(raw)
    if (Array.isArray(arr)) {
      const valid = arr.filter(k => ALL_COLUMNS.some(c => c.key === k))
      if (valid.length) return valid
    }
  } catch { /* localStorage indispo/quota — repli sur le défaut */ }
  return null
}

// Miniature créatif RÉSOLUE à l'affichage (URL fraîche, jamais persistée —
// ADSDEEP12). Une ad vidéo montre une icône (pas de lecture inline dans une
// table) ; une ad image résout sa vraie miniature.
function AdThumbnail({ mediaRef, kind }) {
  const [url, setUrl] = useState('')
  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise avant résolution (changement de mediaRef/kind)
    setUrl('')
    if (mediaRef && kind === 'image') {
      adsengineApi.media.resolve(mediaRef, 'image')
        .then(r => { if (alive) setUrl(r.data?.url || '') })
        .catch(() => { if (alive) setUrl('') })
    }
    return () => { alive = false }
  }, [mediaRef, kind])

  if (!mediaRef) {
    return (
      <span data-testid="ae-cockpit-thumb-empty" aria-label="Aucun créatif miroité"
        style={{ display: 'inline-flex', width: 36, height: 36, alignItems: 'center',
          justifyContent: 'center', background: '#f1f5f9', borderRadius: 6, color: '#94a3b8' }}>
        <ImageOff size={16} aria-hidden="true" />
      </span>
    )
  }
  if (kind === 'video') {
    return (
      <span data-testid="ae-cockpit-thumb-video" aria-label="Créatif vidéo"
        style={{ display: 'inline-flex', width: 36, height: 36, alignItems: 'center',
          justifyContent: 'center', background: '#e0e7ff', borderRadius: 6, color: '#4338ca' }}>
        <Video size={16} aria-hidden="true" />
      </span>
    )
  }
  return url
    ? <img data-testid="ae-cockpit-thumb-image" src={url} alt=""
        style={{ width: 36, height: 36, objectFit: 'cover', borderRadius: 6 }} />
    : <span data-testid="ae-cockpit-thumb-loading" style={{ display: 'inline-block', width: 36, height: 36,
        background: '#f1f5f9', borderRadius: 6 }} />
}

// PUB8 — courbe de rétention (25/50/75/100 %) d'UNE ad vidéo, réutilisant
// l'endpoint de reporting déjà câblé (``reports.scatter`` — ADSDEEP47) plutôt
// qu'un nouvel endpoint : le bundle vidéo complet (metrics.derived_ad_video_
// metrics) y voyage désormais par point (PUB8, reporting.py) au lieu d'être
// jeté après le hook rate. Aucune donnée si l'ad n'est pas vidéo ou n'a pas
// de lecture calculable (jamais un 0 fabriqué).
function AdRetentionCurve({ adMetaId, kind }) {
  const [point, setPoint] = useState(null)
  const [loading, setLoading] = useState(false)

  useEffect(() => {
    let alive = true
    // eslint-disable-next-line react-hooks/set-state-in-effect -- réinitialise avant résolution (changement d'ad)
    setPoint(null)
    if (kind !== 'video' || !adMetaId) return undefined
    setLoading(true)
    adsengineApi.reports.scatter()
      .then(r => {
        if (!alive) return
        const points = Array.isArray(r.data?.points) ? r.data.points : []
        setPoint(points.find(p => p.ad_meta_id === adMetaId) || null)
      })
      .catch(() => { if (alive) setPoint(null) })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [adMetaId, kind])

  if (kind !== 'video') return null
  if (loading) {
    return <p data-testid="ae-cockpit-retention-loading" style={{ color: '#64748b', margin: '0.75rem 0 0' }}>
      Chargement de la rétention…</p>
  }
  const retention = point?.retention
  const values = retention ? [retention.p25, retention.p50, retention.p75, retention.p100] : []
  if (!values.some(v => v != null)) return null

  return (
    <div data-testid="ae-cockpit-retention" style={{ marginTop: '0.75rem' }}>
      <strong style={{ fontSize: '0.85rem', color: '#475569' }}>
        Courbe de rétention (25 / 50 / 75 / 100 %)
      </strong>
      <p style={{ margin: '0.25rem 0 0' }}>
        {values.map(v => formatPercent(v, 0)).join(' · ')}
      </p>
    </div>
  )
}

function fatigueTone(fatigue) {
  if (!fatigue) return { bg: '#f1f5f9', color: '#64748b', label: 'Inconnu' }
  if (fatigue.insufficient_data) return { bg: '#f1f5f9', color: '#64748b', label: 'Historique insuffisant' }
  if (!fatigue.fired) return { bg: '#dcfce7', color: '#166534', label: 'Pas de fatigue' }
  return fatigue.severity === 'critique'
    ? { bg: '#fee2e2', color: '#991b1b', label: 'Fatigue confirmée' }
    : { bg: '#ffedd5', color: '#9a3412', label: 'Fatigue possible' }
}

// PUB43 — dernière vue enregistrée (localStorage), lue UNE FOIS au montage —
// jamais recalculée entre-temps (un `useState(() => ...)` initializer, comme
// `range` ci-dessous).
const initialCockpitView = () => {
  const saved = loadSavedCockpitView()
  return {
    tab: (saved && COCKPIT_VIEWS.some(v => v.key === saved.tab)) ? saved.tab : 'toutes',
    sort: (saved && saved.sort && saved.sort.key && saved.sort.dir)
      ? saved.sort : { key: 'depense_mad', dir: 'desc' },
  }
}

export default function AdsCockpitScreen() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  // PUB43 — vues enregistrées un-clic (Top Ads / En fatigue / En baisse /
  // Meilleures vidéos) + mémoire du dernier onglet/tri (localStorage).
  const [{ tab: activeView, sort }, setViewState] = useState(initialCockpitView)
  const [openAdId, setOpenAdId] = useState(null)
  // FIXPUB8 — le panneau de détail apparaît SOUS le tableau (invisible sans
  // scroll manuel) : on l'amène en vue au clic, jamais au montage initial.
  const detailRef = useRef(null)

  // PUB40 — sélecteur de période + comparaison (partagé avec Dashboard).
  // FIXPUB2 — défaut « Tout » (aucune borne) : contrairement au Dashboard
  // (indicateur du mois en cours), le cockpit liste des ads précises — un
  // fondateur qui cherche une ad d'il y a 2 mois ne doit pas la croire
  // disparue faute d'avoir pensé à élargir la période.
  const [range, setRange] = useState(
    () => ({ preset: 'tout', ...presetRange('tout'), compare: false }))
  const [previousTotal, setPreviousTotal] = useState(null)
  // PUB41 — état-ERREUR distinct de l'état-vide : une panne de synchro ne
  // doit JAMAIS ressembler à « aucune ad » (le silence que ce ticket tue).
  const [loadError, setLoadError] = useState(false)
  // FIXPUB9 — devise du compte Meta (les montants Meta ne sont jamais
  // forcés en MAD) ; 'MAD' en repli tant qu'elle n'est pas connue.
  const [currency, setCurrency] = useState('MAD')
  // DATAPUB5 — colonnes visibles (sélecteur persisté localStorage) + panneau.
  const [visibleKeys, setVisibleKeys] = useState(
    () => loadSavedColumns() || DEFAULT_COLUMN_KEYS)
  const [showColumnMenu, setShowColumnMenu] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    const params = { debut: range.debut || undefined, fin: range.fin || undefined }
    adsengineApi.metrics.adsCockpit(params)
      .then(r => {
        setRows(Array.isArray(r.data) ? r.data : (r.data?.results || []))
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
    const connGet = adsengineApi.connection?.get
    if (connGet) {
      connGet()
        .then(r => setCurrency(r?.data?.currency || 'MAD'))
        .catch(() => {})
    }

    // Comparaison : un second appel sur la période PRÉCÉDENTE (PUB40 — un
    // cockpit ligne-par-ligne n'a pas de bloc `previous` serveur comme le
    // dashboard ; on compare le TOTAL dépense des deux périodes).
    if (range.compare && range.debut && range.fin) {
      const prev = previousRange(range)
      adsengineApi.metrics.adsCockpit({ debut: prev.debut, fin: prev.fin })
        .then(r => setPreviousTotal(
          totalSpend(Array.isArray(r.data) ? r.data : (r.data?.results || []))))
        .catch(() => setPreviousTotal(null))
    } else {
      setPreviousTotal(null)
    }
  }, [range])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // PUB43 — mémorise le dernier onglet/tri choisi (localStorage) à chaque
  // changement — dégradation silencieuse si indisponible (cockpitViews.js).
  useEffect(() => { saveCockpitView({ tab: activeView, sort }) }, [activeView, sort])

  // DATAPUB5 — persiste le choix de colonnes (dégradation silencieuse).
  useEffect(() => {
    try {
      window.localStorage.setItem(COLUMN_STORAGE_KEY, JSON.stringify(visibleKeys))
    } catch { /* localStorage indispo/quota — ignoré */ }
  }, [visibleKeys])

  // Colonnes affichées, dans l'ordre canonique d'ALL_COLUMNS (l'ordre stocké
  // n'influe pas — on ajoute/retire seulement des clés).
  const visibleColumns = useMemo(
    () => ALL_COLUMNS.filter(c => visibleKeys.includes(c.key)), [visibleKeys])

  const toggleColumn = (key) => setVisibleKeys(keys =>
    keys.includes(key) ? keys.filter(k => k !== key) : [...keys, key])

  // FIXPUB8 — fait défiler jusqu'au panneau de détail dès qu'une ligne
  // s'ouvre (jamais au montage : `openAdId` démarre à `null`).
  useEffect(() => {
    if (openAdId != null) {
      detailRef.current?.scrollIntoView({ behavior: 'smooth', block: 'start' })
    }
  }, [openAdId])

  // « Toutes » reste pilotée par le tri MANUEL (colonnes cliquables) ; un
  // onglet prédéfini FIGE son propre filtre+tri (PUB43 — jamais retrié).
  const sortedRows = useMemo(
    () => activeView === 'toutes'
      ? sortCockpitRows(rows, sort.key, sort.dir)
      : applyCockpitView(rows, activeView),
    [rows, sort, activeView])

  const toggleSort = (key) => {
    if (activeView !== 'toutes') return // figé (PUB43) : un onglet prédéfini ne se retrie pas
    setViewState(prev => ({
      tab: prev.tab,
      sort: prev.sort.key === key
        ? { key, dir: prev.sort.dir === 'asc' ? 'desc' : 'asc' }
        : { key, dir: 'asc' },
    }))
  }

  const selectView = (key) => {
    setViewState(prev => ({ ...prev, tab: key }))
    setOpenAdId(null) // la ligne ouverte peut ne plus exister dans la nouvelle vue
  }

  const sortIcon = (key) => {
    if (sort.key !== key) return <ArrowUpDown size={13} aria-hidden="true" />
    return sort.dir === 'asc'
      ? <ArrowUp size={13} aria-hidden="true" />
      : <ArrowDown size={13} aria-hidden="true" />
  }

  const openRow = openAdId != null ? sortedRows.find(r => r.id === openAdId) : null
  const currentTotal = totalSpend(sortedRows)
  const compareDelta = previousTotal != null ? computeDelta(currentTotal, previousTotal) : null

  return (
    <div className="page ae-ads-cockpit">
      <div className="page-header">
        <h2>Cockpit par ad</h2>
      </div>

      {/* FIXPUB4 — bandeau « nouvelle version disponible » (SW existant). */}
      <UpdateBanner />

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {/* PUB40 — sélecteur de période + comparaison. */}
      <DateRangeBar value={range} onChange={setRange} />
      {compareDelta && (
        <p className="card" data-testid="ae-cockpit-compare-summary"
          style={{ padding: '0.6rem 0.9rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
          Dépense totale période : {formatMoney(currentTotal, currency)} ({formatDeltaPct(compareDelta.pct)} vs période précédente)
        </p>
      )}

      {/* PUB43 — vues enregistrées un-clic (filtre+tri figés, mémorisées). */}
      <div className="ae-cockpit-views" data-testid="ae-cockpit-views" role="group"
        aria-label="Vues enregistrées" style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginBottom: '1rem' }}>
        {COCKPIT_VIEWS.map(v => (
          <button key={v.key} type="button"
            className={`btn ${activeView === v.key ? 'btn-primary' : 'btn-light'}`}
            data-testid={`ae-cockpit-view-${v.key}`} aria-pressed={activeView === v.key}
            onClick={() => selectView(v.key)}>
            {v.label}
          </button>
        ))}
      </div>

      {/* DATAPUB5 — sélecteur de colonnes (parité Ads Manager) : toutes les
          métriques détenues, choix persisté (localStorage). */}
      <div className="ae-cockpit-columns" style={{ position: 'relative', marginBottom: '1rem' }}>
        <button type="button" className="btn btn-light"
          data-testid="ae-cockpit-columns-toggle" aria-expanded={showColumnMenu}
          onClick={() => setShowColumnMenu(v => !v)}>
          Colonnes ({visibleColumns.length})
        </button>
        {showColumnMenu && (
          <div data-testid="ae-cockpit-columns-menu" role="group"
            aria-label="Colonnes affichées"
            style={{ position: 'absolute', zIndex: 10, background: '#fff',
              border: '1px solid #e2e8f0', borderRadius: 8, padding: '0.6rem',
              marginTop: '0.3rem', display: 'grid',
              gridTemplateColumns: 'repeat(2, minmax(150px, 1fr))',
              gap: '0.25rem 1rem', boxShadow: '0 4px 12px rgba(0,0,0,0.08)' }}>
            {ALL_COLUMNS.map(col => (
              <label key={col.key} data-testid={`ae-cockpit-column-${col.key}`}
                style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', fontSize: '0.85rem' }}>
                <input type="checkbox" checked={visibleKeys.includes(col.key)}
                  onChange={() => toggleColumn(col.key)} />
                {col.label}
              </label>
            ))}
          </div>
        )}
      </div>

      {/* ADSDEEP66 — fenêtres de données visibles à l'écran : leads (90 j,
          MetaLeadMirror ADSDEEP19) + insights (37 mois, dépense/fréquence). */}
      <DataWindowNotice kind="leads" />
      <DataWindowNotice kind="insights" />

      {/* PUB41 — état-ERREUR distinct de l'état-vide : jamais un silence. */}
      {loadError && (
        <p data-testid="ae-cockpit-load-error" role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
          Chargement du cockpit impossible — panne de synchronisation possible.
          {sortedRows.length > 0 ? ' Liste peut-être obsolète.' : ''}
        </p>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="ae-cockpit-table">
            <thead>
              <tr>
                <th aria-label="Miniature créatif" />
                {visibleColumns.map(col => (
                  <th key={col.key} aria-sort={(activeView === 'toutes' && sort.key === col.key)
                    ? (sort.dir === 'asc' ? 'ascending' : 'descending') : 'none'}>
                    {/* PUB43 — tri par colonne désactivé quand une vue prédéfinie
                        est active (filtre+tri FIGÉS) — jamais un bouton actif
                        qui ne fait rien en silence. */}
                    <button type="button" className="btn-link" data-testid={`ae-cockpit-sort-${col.key}`}
                      onClick={() => toggleSort(col.key)}
                      disabled={activeView !== 'toutes'}
                      title={activeView !== 'toutes' ? 'Tri figé par la vue sélectionnée' : undefined}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem',
                        background: 'none', border: 0, padding: 0, font: 'inherit',
                        cursor: activeView !== 'toutes' ? 'default' : 'pointer',
                        opacity: activeView !== 'toutes' ? 0.55 : 1 }}>
                      {col.label} {activeView === 'toutes' && sortIcon(col.key)}
                    </button>
                  </th>
                ))}
                <th>Fatigue</th>
                <th />
                <th aria-label="Fiche complète" />
              </tr>
            </thead>
            <tbody>
              {sortedRows.map(row => {
                const tone = fatigueTone(row.fatigue)
                return (
                  <tr key={row.id} data-testid="ae-cockpit-row">
                    <td><AdThumbnail mediaRef={row.thumbnail_ref} kind={row.thumbnail_kind} /></td>
                    {visibleColumns.map(col => (
                      <td key={col.key}>{col.render(row, currency)}</td>
                    ))}
                    <td>
                      <span className="badge" data-testid="ae-cockpit-fatigue-badge"
                        style={{ background: tone.bg, color: tone.color }}>
                        {tone.label}
                      </span>
                    </td>
                    <td>
                      <button type="button" className="btn btn-light" data-testid="ae-cockpit-open"
                        onClick={() => setOpenAdId(id => id === row.id ? null : row.id)}>
                        {openAdId === row.id ? 'Fermer' : 'Détail'}
                      </button>
                    </td>
                    <td>
                      {/* PUB44 — lien croisé vers la fiche « histoire complète ». */}
                      <Link to={`/publicite/ad/${row.meta_id}`} className="btn btn-light"
                        data-testid="ae-cockpit-full-story"
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <FileText size={14} aria-hidden="true" /> Fiche complète
                      </Link>
                    </td>
                  </tr>
                )
              })}
              {sortedRows.length === 0 && !loadError && (
                <tr><td colSpan={visibleColumns.length + 4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune ad synchronisée</td></tr>
              )}
            </tbody>
          </table>
        )}

      {openRow && (
        <section ref={detailRef} className="card ae-cockpit-detail" data-testid="ae-cockpit-detail"
          style={{ padding: '1rem', marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>{openRow.nom || openRow.meta_id}</h3>
            <button type="button" className="btn btn-light" data-testid="ae-cockpit-detail-close"
              onClick={() => setOpenAdId(null)}>Fermer</button>
          </div>
          <AdCreativePanel
            adMetaId={openRow.meta_id}
            creative={{
              video_id: openRow.thumbnail_kind === 'video' ? openRow.thumbnail_ref : '',
              image_hash: openRow.thumbnail_kind === 'image' ? openRow.thumbnail_ref : '',
            }}
          />
          {/* PUB22 — proposer une action manuelle sur CETTE ad (pause/renommer…),
              chaque soumission passe par la boîte d'approbation. */}
          <ManualActionMenu
            target={{ metaId: openRow.meta_id, scope: 'ad', name: openRow.nom }}
            onProposed={load} />

          {/* PUB8 — courbe de rétention (ad vidéo uniquement). */}
          <AdRetentionCurve adMetaId={openRow.meta_id} kind={openRow.thumbnail_kind} />

          {/* PUB3 — drill démographie/placement/région/heure de CETTE ad
              (id du miroir, pas le meta_id — même clé que breakdowns/). */}
          <div style={{ marginTop: '1rem' }}>
            <BreakdownsPanel objectType="ad" objectId={openRow.id} />
          </div>
        </section>
      )}
    </div>
  )
}
