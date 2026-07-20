import { useEffect, useState, useCallback } from 'react'
import { Link } from 'react-router-dom'
import { RefreshCw, History, ChevronRight, FileText } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMoney, formatNumber, rankCreatives } from './adsengine'
import DataWindowNotice from './DataWindowNotice'
import ManualActionMenu from './ManualActionMenu'
// PUB3 — panneau démographie/placement/région/heure, construit+testé mais
// jamais monté nulle part avant cette tâche — drill par ad set ET par ad.
import BreakdownsPanel from './BreakdownsPanel'
import { formatDateTime } from '../../lib/format'
import DateRangeBar from './DateRangeBar'
import { presetRange, previousRange, computeDelta, formatDeltaPct } from './dateRange'
import SyncStatusBanner from './SyncStatusBanner'
// FIXPUB4 — bandeau « version périmée » (réutilise le SW existant).
import UpdateBanner from './UpdateBanner'

// PUB40 — dépense totale visible (somme ``depense_mad``/``spend_mad`` des
// campagnes listées) — pure, testable isolément.
function totalCampaignSpend(campaigns) {
  return (campaigns || []).reduce(
    (sum, c) => sum + (Number(c.depense_mad ?? c.spend_mad) || 0), 0)
}

/* ============================================================================
   ENG24 — Écran « Campagnes » (miroirs Meta) du moteur publicitaire.
   ----------------------------------------------------------------------------
   - Liste des miroirs de campagnes (lecture — la création/édition passe par la
     boîte d'approbation, jamais d'écriture directe ici).
   - Bouton « Synchroniser » (sync-now des miroirs depuis Meta).
   - Classement des créatifs par VALEUR business : réponses WhatsApp / coût par
     asset (doctrine P3/P7 — PAS de CTR abstrait). Le tri vit dans
     `rankCreatives` (adsengine.js), l'écran ne fait qu'afficher.

   ADSDEEP60 — le « Détail » d'une campagne n'ouvre plus une fiche plate : il
   charge la HIÉRARCHIE Campagne → Ad sets → Ads (`campaigns.hierarchy`, 3
   niveaux navigables) avec statuts/budgets/dépenses/leads par niveau + le
   badge d'apprentissage (ADSDEEP32) par ad set. Un fil d'Ariane permet de
   remonter d'un niveau sans recharger la liste des campagnes.

   PUB13 — le détail d'un ad set (niveau 3) ne montrait que le badge
   d'apprentissage DÉRIVÉ (learning_badge) ; `learning_stage_info` (dict BRUT
   Meta : conversions, attribution_windows…) et `last_sig_edit` (dernière
   édition significative — reset d'apprentissage) sont sérialisés
   (AdSetMirrorSerializer) mais invisibles. Panneau « Apprentissage Meta » qui
   les rend TELS QUELS (jamais reformatés/interprétés — c'est du brut Meta
   pour l'audit).
   ========================================================================== */

// PUB13 — rend une valeur BRUTE de `learning_stage_info` sans l'interpréter
// (objet/liste → JSON compact, primitive → telle quelle).
function formatLearningValue(v) {
  if (v == null) return '—'
  if (typeof v === 'object') return JSON.stringify(v)
  return String(v)
}

export default function CampaignsScreen() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [ranking, setRanking] = useState([])
  // ADSDEEP19 — comptes de leads RÉELS par campagne (meta_id → nombre).
  const [realLeads, setRealLeads] = useState({})
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  // FIXPUB3 — récupération complète de l'historique (distinct de sync-now,
  // qui ne couvre que la fenêtre habituelle).
  const [backfilling, setBackfilling] = useState(false)
  // Devise du compte Meta (les budgets/dépenses sont dans CETTE devise, souvent
  // USD — jamais forcés en MAD). 'MAD' en repli tant qu'elle n'est pas connue.
  const [currency, setCurrency] = useState('MAD')

  // ADSDEEP60 — hiérarchie de la campagne ouverte (null = liste plate seule).
  const [hierarchy, setHierarchy] = useState(null)
  const [hierarchyLoading, setHierarchyLoading] = useState(false)
  // id du miroir d'ad set actuellement ouvert (3ᵉ niveau = ses ads) ; null =
  // on est encore au niveau « ad sets » de la campagne.
  const [openAdsetId, setOpenAdsetId] = useState(null)
  // PUB3 — drill « Audience & diffusion » (BreakdownsPanel) : id du miroir
  // (ad set OU ad, selon le niveau affiché) dont les ventilations sont
  // ouvertes ; un seul à la fois (les deux tables ne sont jamais visibles
  // simultanément — remis à null à chaque changement de niveau).
  const [openBreakdownId, setOpenBreakdownId] = useState(null)
  const toggleBreakdown = (id) =>
    setOpenBreakdownId(cur => (cur === id ? null : id))

  // PUB40 — sélecteur de période + comparaison (partagé avec Dashboard/Cockpit).
  // FIXPUB2 — défaut « Tout » (aucune borne) : une campagne synchronisée il y
  // a plus de 30 jours ne doit jamais sembler absente à l'ouverture de l'écran.
  const [range, setRange] = useState(
    () => ({ preset: 'tout', ...presetRange('tout'), compare: false }))
  const [previousTotal, setPreviousTotal] = useState(null)
  // PUB41 — état-ERREUR distinct de l'état-vide (jamais un silence).
  const [loadError, setLoadError] = useState(false)

  const load = useCallback(() => {
    setLoading(true)
    const params = { debut: range.debut || undefined, fin: range.fin || undefined }
    adsengineApi.campaigns.list(params)
      .then(r => {
        setCampaigns(Array.isArray(r.data) ? r.data : (r.data?.results || []))
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
    adsengineApi.campaigns.creativeRanking()
      .then(r => setRanking(rankCreatives(Array.isArray(r.data) ? r.data : (r.data?.results || []))))
      .catch(() => setRanking([]))
    // ADSDEEP19 — comptes de leads RÉELS (remplace le « Leads: 0 » des insights).
    const realLeadsFn = adsengineApi.metrics?.realLeads
    if (realLeadsFn) {
      realLeadsFn()
        .then(r => setRealLeads(r?.data?.by_campaign || {}))
        .catch(() => setRealLeads({}))
    }
    const connGet = adsengineApi.connection?.get
    if (connGet) {
      connGet()
        .then(r => setCurrency(r?.data?.currency || 'MAD'))
        .catch(() => {})
    }
    // PUB40 — comparaison : dépense TOTALE de la période précédente.
    if (range.compare && range.debut && range.fin) {
      const prev = previousRange(range)
      adsengineApi.campaigns.list({ debut: prev.debut, fin: prev.fin })
        .then(r => setPreviousTotal(
          totalCampaignSpend(Array.isArray(r.data) ? r.data : (r.data?.results || []))))
        .catch(() => setPreviousTotal(null))
    } else {
      setPreviousTotal(null)
    }
  }, [range])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  // ADSDEEP60 — ouvre la hiérarchie d'une campagne (Ad sets → Ads).
  const openCampaign = (c) => {
    setOpenAdsetId(null)
    setOpenBreakdownId(null)
    setHierarchy({ ...c, adsets: [] }) // affichage immédiat (ligne connue)
    setHierarchyLoading(true)
    adsengineApi.campaigns.hierarchy(c.id)
      .then(r => setHierarchy(r.data || { ...c, adsets: [] }))
      .catch(() => setHierarchy({ ...c, adsets: [] }))
      .finally(() => setHierarchyLoading(false))
  }
  const closeCampaign = () => { setHierarchy(null); setOpenAdsetId(null); setOpenBreakdownId(null) }
  const backToAdsets = () => { setOpenAdsetId(null); setOpenBreakdownId(null) }
  const openAdsetLevel = (id) => { setOpenAdsetId(id); setOpenBreakdownId(null) }

  const syncNow = async () => {
    setSyncing(true); setMsg('')
    try {
      await adsengineApi.campaigns.syncNow()
      setMsg('Synchronisation lancée.')
      load()
    } catch {
      setMsg('Synchronisation impossible.')
    } finally {
      setSyncing(false)
    }
  }

  // FIXPUB3 — « Récupérer tout l'historique » : au-delà de la fenêtre
  // habituelle de sync-now (route posée par la lane backend parallèle).
  const fullBackfill = async () => {
    setBackfilling(true); setMsg('')
    try {
      await adsengineApi.campaigns.fullBackfill()
      setMsg("Récupération de tout l'historique lancée…")
    } catch {
      setMsg("Récupération de tout l'historique impossible.")
    } finally {
      setBackfilling(false)
    }
  }

  const openAdset = openAdsetId != null
    ? (hierarchy?.adsets || []).find(a => a.id === openAdsetId)
    : null

  return (
    <div className="page ae-campaigns">
      <div className="page-header">
        <h2>Campagnes</h2>
        <div style={{ display: 'flex', alignItems: 'center', gap: '0.5rem' }}>
          <button type="button" className="btn btn-primary" data-testid="ae-camp-sync"
            disabled={syncing} onClick={syncNow}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            <RefreshCw size={15} aria-hidden="true" />
            {syncing ? 'Synchronisation…' : 'Synchroniser'}
          </button>
          {/* FIXPUB3 — récupère TOUT l'historique Meta (au-delà de la
              fenêtre habituelle de sync-now). */}
          <button type="button" className="btn btn-light" data-testid="ae-camp-backfill"
            disabled={backfilling} onClick={fullBackfill}
            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
            <History size={15} aria-hidden="true" />
            {backfilling ? 'Récupération…' : "Récupérer tout l'historique"}
          </button>
        </div>
      </div>

      {msg && <p data-testid="ae-camp-msg" style={{ color: '#475569', margin: '0 0 0.75rem' }}>{msg}</p>}

      {/* FIXPUB4 — bandeau « nouvelle version disponible » (SW existant). */}
      <UpdateBanner />

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {/* PUB40 — sélecteur de période + comparaison. */}
      <DateRangeBar value={range} onChange={setRange} />
      {previousTotal != null && (() => {
        const delta = computeDelta(totalCampaignSpend(campaigns), previousTotal)
        return (
          <p className="card" data-testid="ae-camp-compare-summary"
            style={{ padding: '0.6rem 0.9rem', marginBottom: '1rem', fontSize: '0.85rem' }}>
            Dépense totale période : {formatMoney(totalCampaignSpend(campaigns), currency)}
            {' '}({formatDeltaPct(delta.pct)} vs période précédente)
          </p>
        )
      })()}

      {/* ADSDEEP66 — les comptes de leads affichés ici sont bornés à la
          fenêtre Meta 90 j (au-delà, seul l'ERP/Odoo fait foi). */}
      <DataWindowNotice kind="leads" />

      {/* PUB41 — état-ERREUR distinct de l'état-vide : jamais un silence. */}
      {loadError && (
        <p data-testid="ae-camp-load-error" role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
          Chargement des campagnes impossible — panne de synchronisation possible.
          {campaigns.length > 0 ? ' Liste peut-être obsolète.' : ''}
        </p>
      )}

      {/* Liste des miroirs (niveau 1 — campagnes) */}
      {loading
        ? <p className="page-loading">Chargement…</p>
        : (
          <table className="data-table" data-testid="ae-camp-table">
            <thead>
              <tr><th>Campagne</th><th>Statut</th><th>Budget/jour</th><th>Dépense</th><th /></tr>
            </thead>
            <tbody>
              {campaigns.map(c => (
                <tr key={c.id} data-testid="ae-camp-row">
                  <td>{c.nom || c.name}</td>
                  <td>{c.statut_display || c.statut || '—'}</td>
                  <td>{formatMoney(c.budget_quotidien_mad ?? c.daily_budget_mad, currency)}</td>
                  <td>{formatMoney(c.depense_mad ?? c.spend_mad, currency)}</td>
                  <td>
                    <button type="button" className="btn btn-light" data-testid="ae-camp-open"
                      onClick={() => openCampaign(c)}>Détail</button>
                  </td>
                </tr>
              ))}
              {campaigns.length === 0 && !loadError && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune campagne synchronisée</td></tr>
              )}
            </tbody>
          </table>
        )}

      {/* ADSDEEP60 — Hiérarchie Campagne → Ad sets → Ads (niveaux 2 et 3) */}
      {hierarchy && (
        <section className="card ae-camp-hierarchy" data-testid="ae-camp-hierarchy"
          style={{ padding: '1rem', marginTop: '1rem' }}>
          {/* Fil d'Ariane */}
          <nav aria-label="Fil d'Ariane" data-testid="ae-camp-breadcrumb"
            style={{ display: 'flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem',
              color: '#64748b', marginBottom: '0.75rem', flexWrap: 'wrap' }}>
            <button type="button" className="btn-link" data-testid="ae-camp-breadcrumb-campaigns"
              onClick={closeCampaign} style={{ background: 'none', border: 0, padding: 0,
                color: '#2563eb', cursor: 'pointer' }}>Campagnes</button>
            <ChevronRight size={14} aria-hidden="true" />
            {openAdset
              ? (
                <>
                  <button type="button" className="btn-link" data-testid="ae-camp-breadcrumb-campaign"
                    onClick={backToAdsets} style={{ background: 'none', border: 0, padding: 0,
                      color: '#2563eb', cursor: 'pointer' }}>
                    {hierarchy.nom || hierarchy.name}
                  </button>
                  <ChevronRight size={14} aria-hidden="true" />
                  <span>{openAdset.nom || openAdset.name}</span>
                </>
              )
              : <span>{hierarchy.nom || hierarchy.name}</span>}
          </nav>

          {hierarchyLoading
            ? <p className="page-loading">Chargement…</p>
            : !openAdset
              ? (
                <>
                  {/* Détail campagne + niveau 2 (ad sets) */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0 }}>{hierarchy.nom || hierarchy.name}</h3>
                    <button type="button" className="btn btn-light" data-testid="ae-camp-hierarchy-close"
                      onClick={closeCampaign}>Fermer</button>
                  </div>
                  <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.35rem 1rem', margin: '0.75rem 0 1rem' }}>
                    <dt style={{ color: '#64748b' }}>Statut</dt>
                    <dd style={{ margin: 0 }}>{hierarchy.statut_display || hierarchy.statut || '—'}</dd>
                    <dt style={{ color: '#64748b' }}>Objectif</dt>
                    <dd style={{ margin: 0 }}>{hierarchy.objectif || hierarchy.objective || '—'}</dd>
                    <dt style={{ color: '#64748b' }}>Budget/jour</dt>
                    <dd style={{ margin: 0 }}>{formatMoney(hierarchy.budget_quotidien_mad, currency)}</dd>
                    <dt style={{ color: '#64748b' }}>Leads</dt>
                    {/* ADSDEEP19 — compte RÉEL (MetaLeadMirror) prioritaire sur les insights */}
                    <dd style={{ margin: 0 }} data-testid="ae-camp-real-leads">
                      {formatNumber(
                        realLeads[hierarchy.meta_id] ?? hierarchy.nb_leads)}
                    </dd>
                  </dl>

                  {/* PUB22 — proposer une action sur CETTE campagne (plafond,
                      pause, CBO…) : chaque soumission passe par l'approbation. */}
                  <ManualActionMenu
                    target={{ metaId: hierarchy.meta_id, scope: 'campaign', name: hierarchy.nom }} />

                  <h4 style={{ margin: '0 0 0.5rem' }}>Ad sets</h4>
                  {(hierarchy.adsets || []).length === 0
                    ? <p data-testid="ae-camp-adsets-empty" style={{ color: '#64748b' }}>Aucun ad set synchronisé.</p>
                    : (
                      <table className="data-table" data-testid="ae-camp-adsets-table">
                        <thead>
                          <tr>
                            <th>Ad set</th><th>Statut</th><th>Apprentissage</th>
                            <th>Budget/jour</th><th>Dépense</th><th>Leads</th><th /><th />
                          </tr>
                        </thead>
                        <tbody>
                          {hierarchy.adsets.map(a => (
                            <tr key={a.id} data-testid="ae-camp-adset-row">
                              <td>{a.nom || a.name}</td>
                              <td>{a.statut_display || a.status || '—'}</td>
                              <td>
                                <span className="badge" data-testid="ae-camp-adset-learning-badge">
                                  {a.learning_badge?.label || 'Inconnu'}
                                </span>
                              </td>
                              <td>{formatMoney(a.budget_quotidien_mad, currency)}</td>
                              <td>{formatMoney(a.depense_mad, currency)}</td>
                              <td>{formatNumber(a.nb_leads)}</td>
                              <td>
                                {/* PUB3 — drill audience & diffusion de CET ad set */}
                                <button type="button" className="btn btn-light" data-testid="ae-camp-adset-breakdowns"
                                  onClick={() => toggleBreakdown(a.id)}>
                                  {openBreakdownId === a.id ? 'Fermer les ventilations' : 'Ventilations'}
                                </button>
                              </td>
                              <td>
                                <button type="button" className="btn btn-light" data-testid="ae-camp-adset-open"
                                  onClick={() => openAdsetLevel(a.id)}>Ouvrir</button>
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  {openBreakdownId != null && (hierarchy.adsets || []).some(a => a.id === openBreakdownId) && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <BreakdownsPanel objectType="adset" objectId={openBreakdownId} />
                    </div>
                  )}
                </>
              )
              : (
                <>
                  {/* Niveau 3 — ads de l'ad set ouvert */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <h3 style={{ margin: 0 }}>{openAdset.nom || openAdset.name}</h3>
                    <button type="button" className="btn btn-light" data-testid="ae-camp-adset-back"
                      onClick={backToAdsets}>Retour aux ad sets</button>
                  </div>
                  <p style={{ color: '#64748b', margin: '0.5rem 0' }}>
                    Apprentissage : {openAdset.learning_badge?.label || 'Inconnu'}
                  </p>
                  {/* PUB22 — proposer une action sur CET ad set (budget, duplication,
                      horaire, création d'ad…) via la boîte d'approbation. */}
                  <ManualActionMenu
                    target={{ metaId: openAdset.meta_id, scope: 'adset', name: openAdset.nom }} />

                  {/* PUB13 — panneau « Apprentissage Meta » : learning_stage_info
                      brut + last_sig_edit (fenêtres d'attribution, statut
                      d'apprentissage, dernière édition significative). */}
                  <section className="card ae-camp-learning" data-testid="ae-camp-learning-panel"
                    style={{ padding: '0.75rem', margin: '0 0 0.9rem', border: '1px solid #e2e8f0' }}>
                    <h4 style={{ margin: '0 0 0.4rem' }}>Apprentissage Meta</h4>
                    <p style={{ margin: '0 0 0.5rem', color: '#64748b', fontSize: '0.85rem' }}
                      data-testid="ae-camp-learning-last-sig-edit">
                      Dernière édition significative : {openAdset.last_sig_edit
                        ? formatDateTime(openAdset.last_sig_edit) : 'Aucune.'}
                    </p>
                    {Object.keys(openAdset.learning_stage_info || {}).length === 0
                      ? <p data-testid="ae-camp-learning-empty" style={{ color: '#64748b', margin: 0 }}>
                          Aucune info d&apos;apprentissage brute disponible.</p>
                      : (
                        <ul data-testid="ae-camp-learning-raw"
                          style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.25rem', fontSize: '0.85rem' }}>
                          {Object.entries(openAdset.learning_stage_info).map(([k, v]) => (
                            <li key={k} data-testid="ae-camp-learning-row">
                              <strong style={{ color: '#475569' }}>{k}</strong>{' : '}{formatLearningValue(v)}
                            </li>
                          ))}
                        </ul>
                      )}
                  </section>

                  {(openAdset.ads || []).length === 0
                    ? <p data-testid="ae-camp-ads-empty" style={{ color: '#64748b' }}>Aucune ad synchronisée.</p>
                    : (
                      <table className="data-table" data-testid="ae-camp-ads-table">
                        <thead>
                          <tr><th>Ad</th><th>Statut</th><th>Dépense</th><th>Leads</th><th /></tr>
                        </thead>
                        <tbody>
                          {openAdset.ads.map(ad => (
                            <tr key={ad.id} data-testid="ae-camp-ad-row">
                              <td>{ad.nom || ad.name}</td>
                              <td>{ad.statut_display || ad.status || '—'}</td>
                              <td>{formatMoney(ad.depense_mad, currency)}</td>
                              <td>{formatNumber(ad.nb_leads)}</td>
                              <td>
                                {/* PUB3 — drill audience & diffusion de CETTE ad */}
                                <button type="button" className="btn btn-light" data-testid="ae-camp-ad-breakdowns"
                                  onClick={() => toggleBreakdown(ad.id)}>
                                  {openBreakdownId === ad.id ? 'Fermer les ventilations' : 'Ventilations'}
                                </button>
                                {/* PUB44 — lien croisé vers la fiche « histoire complète ». */}
                                {ad.meta_id && (
                                  <Link to={`/publicite/ad/${ad.meta_id}`} className="btn btn-light"
                                    data-testid="ae-camp-ad-full-story"
                                    style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                                    <FileText size={14} aria-hidden="true" /> Fiche
                                  </Link>
                                )}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    )}
                  {openBreakdownId != null && (openAdset.ads || []).some(ad => ad.id === openBreakdownId) && (
                    <div style={{ marginTop: '0.75rem' }}>
                      <BreakdownsPanel objectType="ad" objectId={openBreakdownId} />
                    </div>
                  )}
                </>
              )}
        </section>
      )}

      {/* Classement des créatifs par valeur (réponses WhatsApp / coût) */}
      <section className="card ae-camp-ranking" data-testid="ae-camp-ranking"
        style={{ padding: '1rem', marginTop: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem' }}>Classement des créatifs — réponses WhatsApp / coût</h3>
        {ranking.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Aucune donnée de créatif.</p>
          : (
            <table className="data-table" data-testid="ae-camp-ranking-table">
              <thead>
                <tr><th>#</th><th>Créatif</th><th>Réponses WhatsApp</th><th>Coût</th><th>Coût / réponse</th></tr>
              </thead>
              <tbody>
                {ranking.map((c, i) => (
                  <tr key={c.id ?? i} data-testid="ae-camp-ranking-row">
                    <td>{i + 1}</td>
                    <td>{c.nom || c.name || c.designation || '—'}</td>
                    <td>{formatNumber(c._reponses)}</td>
                    <td>{formatMoney(c._cout, currency)}</td>
                    <td>{c._coutParReponse == null ? '—' : formatMoney(c._coutParReponse, currency)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </div>
  )
}
