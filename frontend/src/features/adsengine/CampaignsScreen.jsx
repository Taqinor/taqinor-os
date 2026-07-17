import { useEffect, useState, useCallback } from 'react'
import { RefreshCw } from 'lucide-react'
import adsengineApi from './adsengineApi'
import { formatMoney, formatNumber, rankCreatives } from './adsengine'

/* ============================================================================
   ENG24 — Écran « Campagnes » (miroirs Meta) du moteur publicitaire.
   ----------------------------------------------------------------------------
   - Liste des miroirs de campagnes (lecture — la création/édition passe par la
     boîte d'approbation, jamais d'écriture directe ici) + détail au clic.
   - Bouton « Synchroniser » (sync-now des miroirs depuis Meta).
   - Classement des créatifs par VALEUR business : réponses WhatsApp / coût par
     asset (doctrine P3/P7 — PAS de CTR abstrait). Le tri vit dans
     `rankCreatives` (adsengine.js), l'écran ne fait qu'afficher.
   ========================================================================== */

export default function CampaignsScreen() {
  const [campaigns, setCampaigns] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null) // détail chargé
  const [ranking, setRanking] = useState([])
  // ADSDEEP19 — comptes de leads RÉELS par campagne (meta_id → nombre).
  const [realLeads, setRealLeads] = useState({})
  const [syncing, setSyncing] = useState(false)
  const [msg, setMsg] = useState('')
  // Devise du compte Meta (les budgets/dépenses sont dans CETTE devise, souvent
  // USD — jamais forcés en MAD). 'MAD' en repli tant qu'elle n'est pas connue.
  const [currency, setCurrency] = useState('MAD')

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.campaigns.list()
      .then(r => setCampaigns(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setCampaigns([]))
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
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const openDetail = (c) => {
    setSelected(c) // affichage immédiat de la ligne connue
    adsengineApi.campaigns.get(c.id)
      .then(r => setSelected(r.data || c))
      .catch(() => { /* on garde la ligne de liste */ })
  }

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

  return (
    <div className="page ae-campaigns">
      <div className="page-header">
        <h2>Campagnes</h2>
        <button type="button" className="btn btn-primary" data-testid="ae-camp-sync"
          disabled={syncing} onClick={syncNow}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          <RefreshCw size={15} aria-hidden="true" />
          {syncing ? 'Synchronisation…' : 'Synchroniser'}
        </button>
      </div>

      {msg && <p data-testid="ae-camp-msg" style={{ color: '#475569', margin: '0 0 0.75rem' }}>{msg}</p>}

      {/* Liste des miroirs */}
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
                      onClick={() => openDetail(c)}>Détail</button>
                  </td>
                </tr>
              ))}
              {campaigns.length === 0 && (
                <tr><td colSpan={5} style={{ textAlign: 'center', color: '#64748b' }}>
                  Aucune campagne synchronisée</td></tr>
              )}
            </tbody>
          </table>
        )}

      {/* Détail de la campagne sélectionnée */}
      {selected && (
        <section className="card ae-camp-detail" data-testid="ae-camp-detail"
          style={{ padding: '1rem', marginTop: '1rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <h3 style={{ margin: 0 }}>{selected.nom || selected.name}</h3>
            <button type="button" className="btn btn-light" onClick={() => setSelected(null)}>Fermer</button>
          </div>
          <dl style={{ display: 'grid', gridTemplateColumns: 'auto 1fr', gap: '0.35rem 1rem', margin: '0.75rem 0 0' }}>
            <dt style={{ color: '#64748b' }}>Statut</dt>
            <dd style={{ margin: 0 }}>{selected.statut_display || selected.statut || '—'}</dd>
            <dt style={{ color: '#64748b' }}>Objectif</dt>
            <dd style={{ margin: 0 }}>{selected.objectif || selected.objective || '—'}</dd>
            <dt style={{ color: '#64748b' }}>Budget/jour</dt>
            <dd style={{ margin: 0 }}>{formatMoney(selected.budget_quotidien_mad ?? selected.daily_budget_mad, currency)}</dd>
            <dt style={{ color: '#64748b' }}>Leads</dt>
            {/* ADSDEEP19 — compte RÉEL (MetaLeadMirror) prioritaire sur les
                insights ; repli sur nb_leads si la clé de campagne est absente. */}
            <dd style={{ margin: 0 }} data-testid="ae-camp-real-leads">
              {formatNumber(
                realLeads[selected.meta_id] ?? realLeads[selected.campaign_meta_id]
                ?? selected.nb_leads ?? selected.leads)}
            </dd>
          </dl>
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
