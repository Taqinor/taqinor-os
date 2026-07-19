import { useEffect, useState, useCallback } from 'react'
import { useParams, Link } from 'react-router-dom'
import {
  ArrowLeft, Layers, MessagesSquare, SlidersHorizontal, FlaskConical, BarChart3,
} from 'lucide-react'
import adsengineApi from './adsengineApi'
import { normalizeAdFullStory } from './adFullStory'
import { formatMAD, formatNumber, formatRatio } from './adsengine'
import AdCreativePanel from './AdCreativePanel'
import SyncStatusBanner from './SyncStatusBanner'

/* ============================================================================
   PUB44 — Fiche « histoire complète » d'une ad (``/publicite/ad/:id``).
   ----------------------------------------------------------------------------
   Doctrine (Done) : « que se passe-t-il avec CETTE ad » se répond en UNE
   page — créatif, dépense/leads/signatures, actions passées, commentaires,
   règles l'ayant touchée, expériences, ventilations, aujourd'hui éclaté sur
   6 écrans. UN SEUL appel réseau (``ads.fullStory``, agrégateur mince côté
   backend — ``metrics.ad_full_story`` réutilise ``ads_cockpit_rows`` +
   les mêmes filtres que Breakdowns/Comments, aucune logique dupliquée ici).
   Chaque section reste un LIEN vers son écran complet pour agir (cet écran
   est une VUE, jamais une nouvelle surface d'action).
   ========================================================================== */

function fatigueTone(fatigue) {
  if (!fatigue) return { bg: '#f1f5f9', color: '#64748b', label: 'Inconnu' }
  if (fatigue.insufficient_data) return { bg: '#f1f5f9', color: '#64748b', label: 'Historique insuffisant' }
  if (!fatigue.fired) return { bg: '#dcfce7', color: '#166534', label: 'Pas de fatigue' }
  return fatigue.severity === 'critique'
    ? { bg: '#fee2e2', color: '#991b1b', label: 'Fatigue confirmée' }
    : { bg: '#ffedd5', color: '#9a3412', label: 'Fatigue possible' }
}

const EMPTY_STORY = normalizeAdFullStory(null)

export default function AdDetailScreen() {
  const { id: metaId } = useParams()
  const [story, setStory] = useState(EMPTY_STORY)
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [notFound, setNotFound] = useState(false)

  const load = useCallback(() => {
    if (!metaId) return
    setLoading(true)
    setNotFound(false)
    adsengineApi.ads.fullStory(metaId)
      .then(r => {
        setStory(normalizeAdFullStory(r.data))
        setLoadError(false)
      })
      .catch(e => {
        if (e?.response?.status === 404) setNotFound(true)
        else setLoadError(true)
      })
      .finally(() => setLoading(false))
  }, [metaId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / changement d'id
  useEffect(() => { load() }, [load])

  if (loading) {
    return (
      <div className="page ae-ad-detail">
        <p className="page-loading">Chargement…</p>
      </div>
    )
  }

  if (notFound) {
    return (
      <div className="page ae-ad-detail">
        <p data-testid="ae-ad-detail-not-found" style={{ color: '#64748b' }}>
          Ad introuvable.
        </p>
        <Link to="/publicite/cockpit" className="btn btn-light">Retour au cockpit</Link>
      </div>
    )
  }

  const { ad, creatif, metriques, actions, commentaires, regles, experiences, breakdowns } = story
  const tone = fatigueTone(metriques?.fatigue)

  return (
    <div className="page ae-ad-detail">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', gap: '0.6rem' }}>
        <Link to="/publicite/cockpit" aria-label="Retour au cockpit"
          style={{ display: 'inline-flex', alignItems: 'center', color: '#475569' }}>
          <ArrowLeft size={18} aria-hidden="true" />
        </Link>
        <h2 style={{ margin: 0 }}>{ad.nom}</h2>
        <span className="badge" data-testid="ae-ad-detail-statut" style={{ background: '#eef2ff', color: '#3730a3' }}>
          {ad.statut_display}
        </span>
      </div>

      <SyncStatusBanner />

      {loadError && (
        <p data-testid="ae-ad-detail-load-error" role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
          Chargement de la fiche impossible — panne de synchronisation possible.
        </p>
      )}

      {/* ── Créatif ── */}
      <section className="card" style={{ padding: '1rem', marginBottom: '1rem' }}>
        {creatif
          ? <AdCreativePanel adMetaId={ad.meta_id} creative={creatif} />
          : <p data-testid="ae-ad-detail-no-creative" style={{ color: '#64748b', margin: 0 }}>
              Aucun créatif synchronisé pour cette ad.</p>}
      </section>

      {/* ── Métriques (MÊME ligne que le cockpit) ── */}
      <section className="card" data-testid="ae-ad-detail-metrics" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <h3 style={{ margin: '0 0 0.6rem' }}>Métriques</h3>
        {metriques
          ? (
            <>
              <div style={{ display: 'grid', gap: '0.75rem',
                gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))' }}>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>Dépense</div>
                  <div style={{ fontWeight: 700 }}>{formatMAD(metriques.depense_mad)}</div></div>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>Leads</div>
                  <div style={{ fontWeight: 700 }}>{formatNumber(metriques.nb_leads)}</div></div>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>CPL</div>
                  <div style={{ fontWeight: 700 }}>{metriques.cpl_mad == null ? '—' : formatMAD(metriques.cpl_mad)}</div></div>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>Signatures</div>
                  <div style={{ fontWeight: 700 }}>{formatNumber(metriques.signatures)}</div></div>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>Coût / signature</div>
                  <div style={{ fontWeight: 700 }}>
                    {metriques.cost_per_signature_mad == null ? '—' : formatMAD(metriques.cost_per_signature_mad)}
                  </div></div>
                <div><div style={{ color: '#64748b', fontSize: '0.8rem' }}>Fréquence</div>
                  <div style={{ fontWeight: 700 }}>{metriques.frequency == null ? '—' : formatRatio(metriques.frequency)}</div></div>
              </div>
              <span className="badge" data-testid="ae-ad-detail-fatigue" style={{ background: tone.bg, color: tone.color, marginTop: '0.6rem', display: 'inline-block' }}>
                {tone.label}
              </span>
            </>
          )
          : <p style={{ color: '#64748b', margin: 0 }}>Aucune métrique disponible.</p>}
      </section>

      {/* ── Actions passées ── */}
      <section className="card" data-testid="ae-ad-detail-actions" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Actions passées</h3>
          <Link to="/publicite/journal" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', color: '#2563eb' }}>
            <Layers size={14} aria-hidden="true" /> Journal complet
          </Link>
        </div>
        {actions.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Aucune action enregistrée sur cette ad.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
              {actions.map(a => (
                <li key={a.id} data-testid="ae-ad-detail-action-row" style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '0.4rem' }}>
                  <strong>{a.kind_display}</strong>{' '}
                  <span className="badge" style={{ background: '#f1f5f9', color: '#475569' }}>{a.status_display}</span>
                  {a.reason_fr && <p style={{ margin: '0.2rem 0 0', color: '#334155' }}>{a.reason_fr}</p>}
                </li>
              ))}
            </ul>
          )}
      </section>

      {/* ── Commentaires ── */}
      <section className="card" data-testid="ae-ad-detail-comments" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Commentaires</h3>
          <Link to="/publicite/commentaires" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', color: '#2563eb' }}>
            <MessagesSquare size={14} aria-hidden="true" /> Boîte de réception
          </Link>
        </div>
        {commentaires.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Aucun commentaire sur cette ad.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
              {commentaires.map(c => (
                <li key={c.id} data-testid="ae-ad-detail-comment-row" style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '0.4rem' }}>
                  <strong>{c.from_name || 'Anonyme'}</strong>
                  <p style={{ margin: '0.2rem 0 0', color: '#334155' }}>{c.message || '(sans texte)'}</p>
                </li>
              ))}
            </ul>
          )}
      </section>

      {/* ── Règles l'ayant touchée ── */}
      <section className="card" data-testid="ae-ad-detail-rules" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Règles l&apos;ayant touchée</h3>
          <Link to="/publicite/regles" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', color: '#2563eb' }}>
            <SlidersHorizontal size={14} aria-hidden="true" /> Règles &amp; anomalies
          </Link>
        </div>
        {regles.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Aucune règle n&apos;a touché cette ad.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
              {regles.map(r => (
                <li key={r.id} data-testid="ae-ad-detail-rule-row" style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '0.4rem' }}>
                  <strong>{r.rule_label || r.kind_display}</strong>
                  {r.message_fr && <p style={{ margin: '0.2rem 0 0', color: '#334155' }}>{r.message_fr}</p>}
                </li>
              ))}
            </ul>
          )}
      </section>

      {/* ── Expériences ── */}
      <section className="card" data-testid="ae-ad-detail-experiments" style={{ padding: '1rem', marginBottom: '1rem' }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '0.5rem' }}>
          <h3 style={{ margin: 0 }}>Expériences</h3>
          <Link to="/publicite/experimentations" style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.85rem', color: '#2563eb' }}>
            <FlaskConical size={14} aria-hidden="true" /> Expérimentations
          </Link>
        </div>
        {experiences.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Cette ad ne participe à aucune expérience.</p>
          : (
            <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.5rem' }}>
              {experiences.map(e => (
                <li key={e.id} data-testid="ae-ad-detail-experiment-row" style={{ borderBottom: '1px solid #f1f5f9', paddingBottom: '0.4rem' }}>
                  <strong>{e.experiment_nom || 'Expérience'}</strong> — {e.label}
                  {!e.is_active && <span className="badge" style={{ marginLeft: '0.4rem', background: '#f1f5f9', color: '#64748b' }}>Inactif</span>}
                </li>
              ))}
            </ul>
          )}
      </section>

      {/* ── Ventilations ── */}
      <section className="card" data-testid="ae-ad-detail-breakdowns" style={{ padding: '1rem' }}>
        <h3 style={{ margin: '0 0 0.5rem', display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <BarChart3 size={16} aria-hidden="true" /> Ventilations
        </h3>
        {breakdowns.length === 0
          ? <p style={{ color: '#64748b', margin: 0 }}>Aucune ventilation disponible.</p>
          : (
            <table className="data-table">
              <thead><tr><th>Dimension</th><th>Clé</th><th>Date</th><th>Dépense</th></tr></thead>
              <tbody>
                {breakdowns.map(b => (
                  <tr key={b.id} data-testid="ae-ad-detail-breakdown-row">
                    <td>{b.dimension_display || b.dimension}</td>
                    <td>{b.key}</td>
                    <td>{b.date}</td>
                    <td>{formatMAD(b.spend)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
      </section>
    </div>
  )
}
