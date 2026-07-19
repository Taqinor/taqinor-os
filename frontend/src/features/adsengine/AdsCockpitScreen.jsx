import { useEffect, useState, useCallback, useMemo } from 'react'
import { Link } from 'react-router-dom'
import { ArrowDown, ArrowUp, ArrowUpDown, Video, ImageOff, FileText } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMAD, formatNumber, formatRatio, sortCockpitRows } from './adsengine'
import DataWindowNotice from './DataWindowNotice'
import AdCreativePanel from './AdCreativePanel'
import DateRangeBar from './DateRangeBar'
import { presetRange, previousRange, computeDelta, formatDeltaPct } from './dateRange'
import SyncStatusBanner from './SyncStatusBanner'
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

const COLUMNS = [
  { key: 'nom', label: 'Ad', sortable: true },
  { key: 'statut_display', label: 'Statut / apprentissage', sortable: true },
  { key: 'depense_mad', label: 'Dépense', sortable: true },
  { key: 'conversations', label: 'Conversations', sortable: true },
  { key: 'nb_leads', label: 'Leads', sortable: true },
  { key: 'cpl_mad', label: 'CPL', sortable: true },
  { key: 'signatures', label: 'Signatures', sortable: true },
  { key: 'cost_per_signature_mad', label: 'Coût / signature', sortable: true },
  { key: 'frequency', label: 'Fréquence', sortable: true },
]

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

  // PUB40 — sélecteur de période + comparaison (partagé avec Dashboard).
  const [range, setRange] = useState(
    () => ({ preset: '30j', ...presetRange('30j'), compare: false }))
  const [previousTotal, setPreviousTotal] = useState(null)
  // PUB41 — état-ERREUR distinct de l'état-vide : une panne de synchro ne
  // doit JAMAIS ressembler à « aucune ad » (le silence que ce ticket tue).
  const [loadError, setLoadError] = useState(false)

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

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {/* PUB40 — sélecteur de période + comparaison. */}
      <DateRangeBar value={range} onChange={setRange} />
      {compareDelta && (
        <p className="card" data-testid="ae-cockpit-compare-summary"
          style={{ padding: '0.6rem 0.9rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
          Dépense totale période : {formatMAD(currentTotal)} ({formatDeltaPct(compareDelta.pct)} vs période précédente)
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
                {COLUMNS.map(col => (
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
                    <td>{row.nom || '—'}</td>
                    <td>
                      {row.statut_display || '—'}{' '}
                      <span className="badge" data-testid="ae-cockpit-learning-badge">
                        {row.learning_badge?.label || 'Inconnu'}
                      </span>
                    </td>
                    <td>{formatMAD(row.depense_mad)}</td>
                    <td>{formatNumber(row.conversations)}</td>
                    <td>{formatNumber(row.nb_leads)}</td>
                    <td>{row.cpl_mad == null ? '—' : formatMAD(row.cpl_mad)}</td>
                    <td>{formatNumber(row.signatures)}</td>
                    <td>{row.cost_per_signature_mad == null ? '—' : formatMAD(row.cost_per_signature_mad)}</td>
                    <td>{row.frequency == null ? '—' : formatRatio(row.frequency)}</td>
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
                <tr><td colSpan={COLUMNS.length + 4} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune ad synchronisée</td></tr>
              )}
            </tbody>
          </table>
        )}

      {openRow && (
        <section className="card ae-cockpit-detail" data-testid="ae-cockpit-detail"
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
        </section>
      )}
    </div>
  )
}
