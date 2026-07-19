import { useState, useCallback, useMemo } from 'react'
import {
  MessagesSquare, EyeOff, Eye, Reply, Trash2, Send, ShieldCheck,
  AlertTriangle, Filter, RefreshCw,
} from 'lucide-react'
import adsengineApi from './adsengineApi'
import SyncStatusBanner from './SyncStatusBanner'
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'

/* ============================================================================
   ADSDEEP54 — Boîte de réception des commentaires (posts + dark posts).
   ----------------------------------------------------------------------------
   Fil CHRONOLOGIQUE filtrable (par ad/post, masqués, non répondus) des
   commentaires miroités (organiques + dark posts), avec actions INLINE. Doctrine
   règle #3 : chaque action (masquer / répondre / supprimer / réponse privée) ne
   fait que PROPOSER une `EngineAction` — l'application réelle passe par la boîte
   d'approbation. Le masquage est RE-VÉRIFIÉ côté backend (read-back) : le badge
   « caché-vérifié » ne s'affiche QUE quand `hidden_verified` est vrai (un masqué
   non confirmé reste marqué « non vérifié »). Un compteur par objet alimente le
   cockpit (total / non répondus / masqués).

   PUB41 — sondage doux (30 s, suspendu onglet masqué) : un commentaire arrivé
   entre deux visites doit apparaître sans rafraîchissement manuel. Panne
   réseau -> `loadError` (message dédié, JAMAIS confondu avec « aucun
   commentaire », le silence que ce ticket tue).
   ========================================================================== */

// Fenêtre Meta d'une réponse privée (miroir de PRIVATE_REPLY_WINDOW_DAYS backend).
const PRIVATE_REPLY_WINDOW_DAYS = 7
const COMMENTS_POLL_MS = 30000

function withinPrivateReplyWindow(createdTime) {
  if (!createdTime) return true
  const created = new Date(createdTime).getTime()
  if (Number.isNaN(created)) return true
  const ageDays = (Date.now() - created) / (1000 * 60 * 60 * 24)
  return ageDays < PRIVATE_REPLY_WINDOW_DAYS
}

export default function CommentsInboxScreen() {
  const [comments, setComments] = useState([])
  const [loading, setLoading] = useState(true)
  const [loadError, setLoadError] = useState(false)
  const [objectFilter, setObjectFilter] = useState('all')
  const [showHiddenOnly, setShowHiddenOnly] = useState(false)
  const [unansweredOnly, setUnansweredOnly] = useState(false)
  const [replyingId, setReplyingId] = useState(null)
  const [replyMode, setReplyMode] = useState('public') // public | private
  const [replyText, setReplyText] = useState('')
  const [proposed, setProposed] = useState(() => new Set())
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    adsengineApi.comments.list()
      .then(r => {
        setComments(Array.isArray(r.data) ? r.data : (r.data?.results || []))
        setLoadError(false)
      })
      .catch(() => setLoadError(true))
      .finally(() => setLoading(false))
  }, [])

  // PUB41 — amorçage immédiat (comme l'ancien `useEffect(load)`) + sondage
  // doux toutes les `COMMENTS_POLL_MS`, suspendu onglet masqué (VX56).
  const { resume } = useVisibilityAwarePolling(
    [{ fn: load, intervalMs: COMMENTS_POLL_MS }])

  // Objets distincts (posts / dark posts) pour le filtre.
  const objectOptions = useMemo(() => {
    const set = new Map()
    comments.forEach(c => {
      const key = c.object_meta_id || '—'
      if (!set.has(key)) set.set(key, c.source || 'post')
    })
    return Array.from(set.entries())
  }, [comments])

  // Fil CHRONOLOGIQUE (plus récent d'abord) + filtres.
  const visible = useMemo(() => {
    let rows = [...comments]
    if (objectFilter !== 'all') rows = rows.filter(c => (c.object_meta_id || '—') === objectFilter)
    if (showHiddenOnly) rows = rows.filter(c => c.is_hidden)
    if (unansweredOnly) rows = rows.filter(c => !c.answered && !c.is_hidden)
    rows.sort((a, b) => {
      const ta = a.created_time ? new Date(a.created_time).getTime() : 0
      const tb = b.created_time ? new Date(b.created_time).getTime() : 0
      return tb - ta
    })
    return rows
  }, [comments, objectFilter, showHiddenOnly, unansweredOnly])

  // Compteur pour le cockpit (sur le périmètre du filtre objet, avant les toggles).
  const counters = useMemo(() => {
    const scope = objectFilter === 'all'
      ? comments
      : comments.filter(c => (c.object_meta_id || '—') === objectFilter)
    return {
      total: scope.length,
      unanswered: scope.filter(c => !c.answered && !c.is_hidden).length,
      hidden: scope.filter(c => c.is_hidden).length,
    }
  }, [comments, objectFilter])

  const markProposed = (id) => setProposed(s => new Set(s).add(id))

  const runAction = async (fn, id) => {
    setBusy(true); setErr('')
    try {
      await fn()
      markProposed(id)
      setReplyingId(null); setReplyText('')
    } catch {
      setErr("Action impossible (permission ?). Rien n'a été proposé.")
    } finally {
      setBusy(false)
    }
  }

  const proposeHide = (c) =>
    runAction(() => adsengineApi.comments.proposeHide(c.id, { hidden: !c.is_hidden }), c.id)
  const proposeDelete = (c) =>
    runAction(() => adsengineApi.comments.proposeDelete(c.id), c.id)
  const submitReply = (c) => {
    const text = replyText.trim()
    if (!text) return
    const call = replyMode === 'private'
      ? adsengineApi.comments.proposePrivateReply(c.id, { message: text })
      : adsengineApi.comments.proposeReply(c.id, { message: text })
    return runAction(() => call, c.id)
  }

  const openReply = (id, mode) => {
    setReplyingId(id); setReplyMode(mode); setReplyText('')
  }

  return (
    <div className="page ae-comments-inbox">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <MessagesSquare size={20} aria-hidden="true" /> Commentaires
        </h2>
        {/* PUB41 — reprise manuelle du sondage (ex. après une panne prolongée). */}
        <button type="button" className="btn btn-light" data-testid="ae-comments-refresh"
          onClick={resume}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <RefreshCw size={15} aria-hidden="true" /> Actualiser
        </button>
      </div>

      {/* PUB41 — bandeau global « Meta ne répond plus… » (fraîcheur/panne). */}
      <SyncStatusBanner />

      {/* PUB41 — état-ERREUR distinct de l'état-vide : jamais un silence. */}
      {loadError && (
        <p data-testid="ae-comments-load-error" role="alert" style={{ color: '#dc2626', margin: '0 0 0.75rem' }}>
          Chargement des commentaires impossible — panne de synchronisation possible.
          {comments.length > 0 ? ' Liste peut-être obsolète (nouvelle tentative automatique en cours).' : ''}
        </p>
      )}

      {/* Compteur cockpit */}
      <div className="ae-comment-counters" data-testid="ae-comment-counters"
        style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', margin: '0 0 1rem' }}>
        <span data-testid="ae-count-total" className="ae-counter-chip"
          style={{ background: '#eef2ff', color: '#3730a3', borderRadius: 999, padding: '0.25rem 0.7rem', fontSize: '0.85rem' }}>
          {counters.total} au total
        </span>
        <span data-testid="ae-count-unanswered" className="ae-counter-chip"
          style={{ background: '#fef3c7', color: '#92400e', borderRadius: 999, padding: '0.25rem 0.7rem', fontSize: '0.85rem' }}>
          {counters.unanswered} non répondu(s)
        </span>
        <span data-testid="ae-count-hidden" className="ae-counter-chip"
          style={{ background: '#f1f5f9', color: '#475569', borderRadius: 999, padding: '0.25rem 0.7rem', fontSize: '0.85rem' }}>
          {counters.hidden} masqué(s)
        </span>
      </div>

      {/* Filtres */}
      <div className="ae-comment-filters" style={{ display: 'flex', gap: '0.75rem', flexWrap: 'wrap', alignItems: 'center', marginBottom: '1rem' }}>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem' }}>
          <Filter size={15} aria-hidden="true" />
          <span style={{ fontSize: '0.85rem', color: '#475569' }}>Objet</span>
          <select className="form-input ae-filter-object" data-testid="ae-filter-object"
            value={objectFilter} onChange={e => setObjectFilter(e.target.value)}>
            <option value="all">Tous</option>
            {objectOptions.map(([id, src]) => (
              <option key={id} value={id}>
                {src === 'ad' ? 'Pub' : 'Post'} · {id}
              </option>
            ))}
          </select>
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
          <input type="checkbox" data-testid="ae-filter-hidden"
            checked={showHiddenOnly} onChange={e => setShowHiddenOnly(e.target.checked)} />
          Masqués seulement
        </label>
        <label style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem', fontSize: '0.85rem' }}>
          <input type="checkbox" data-testid="ae-filter-unanswered"
            checked={unansweredOnly} onChange={e => setUnansweredOnly(e.target.checked)} />
          Non répondus seulement
        </label>
      </div>

      {err && <p data-testid="ae-comments-err" style={{ color: '#dc2626' }}>{err}</p>}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : visible.length === 0
          ? (!loadError && (
              <p data-testid="ae-comments-empty" style={{ color: '#64748b' }}>
                Aucun commentaire à afficher.</p>
            ))
          : (
            <div style={{ display: 'grid', gap: '0.75rem' }}>
              {visible.map(c => {
                const privReplyBlocked = !!c.private_reply_sent_at || !withinPrivateReplyWindow(c.created_time)
                return (
                  <article key={c.id} className="card ae-comment-card" data-testid="ae-comment-card"
                    data-object={c.object_meta_id || ''} data-source={c.source || 'post'}
                    style={{ padding: '0.85rem', border: '1px solid #e2e8f0', opacity: c.is_hidden ? 0.75 : 1 }}>
                    <div style={{ display: 'flex', justifyContent: 'space-between', gap: '0.5rem', flexWrap: 'wrap' }}>
                      <strong style={{ color: '#0f172a' }}>{c.from_name || 'Anonyme'}</strong>
                      <div style={{ display: 'flex', gap: '0.35rem', alignItems: 'center', flexWrap: 'wrap' }}>
                        <span style={{ fontSize: '0.75rem', color: '#94a3b8' }}>
                          {c.source === 'ad' ? 'Pub (dark post)' : 'Post'}
                        </span>
                        {/* Badge « caché-vérifié » — UNIQUEMENT si le read-back a confirmé. */}
                        {c.is_hidden && c.hidden_verified && (
                          <span className="ae-badge-hidden-verified" data-testid={`ae-hidden-verified-${c.id}`}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                              background: '#dcfce7', color: '#166534', borderRadius: 999, padding: '0.15rem 0.55rem', fontSize: '0.75rem' }}>
                            <ShieldCheck size={12} aria-hidden="true" /> Caché — vérifié
                          </span>
                        )}
                        {c.is_hidden && !c.hidden_verified && (
                          <span className="ae-badge-hidden-unverified" data-testid={`ae-hidden-unverified-${c.id}`}
                            style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem',
                              background: '#fef9c3', color: '#854d0e', borderRadius: 999, padding: '0.15rem 0.55rem', fontSize: '0.75rem' }}>
                            <AlertTriangle size={12} aria-hidden="true" /> Caché — non vérifié
                          </span>
                        )}
                        {c.answered && (
                          <span data-testid={`ae-answered-${c.id}`}
                            style={{ background: '#e0f2fe', color: '#075985', borderRadius: 999, padding: '0.15rem 0.55rem', fontSize: '0.75rem' }}>
                            Répondu
                          </span>
                        )}
                      </div>
                    </div>

                    <p data-testid="ae-comment-message" style={{ margin: '0.4rem 0', color: '#334155' }}>
                      {c.message || <em style={{ color: '#94a3b8' }}>(sans texte)</em>}
                    </p>

                    {proposed.has(c.id) && (
                      <p data-testid={`ae-proposed-${c.id}`} style={{ margin: '0.2rem 0', color: '#7c3aed', fontSize: '0.8rem' }}>
                        Proposé — à approuver dans la boîte d&apos;approbation.
                      </p>
                    )}

                    {/* Actions INLINE (chacune = une PROPOSITION) */}
                    <div style={{ display: 'flex', gap: '0.4rem', flexWrap: 'wrap', marginTop: '0.4rem' }}>
                      <button type="button" className="btn btn-light ae-comment-hide"
                        data-testid={`ae-comment-hide-${c.id}`} disabled={busy}
                        onClick={() => proposeHide(c)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        {c.is_hidden
                          ? <><Eye size={14} aria-hidden="true" /> Démasquer</>
                          : <><EyeOff size={14} aria-hidden="true" /> Masquer</>}
                      </button>
                      <button type="button" className="btn btn-light ae-comment-reply"
                        data-testid={`ae-comment-reply-${c.id}`} disabled={busy}
                        onClick={() => openReply(c.id, 'public')}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Reply size={14} aria-hidden="true" /> Répondre
                      </button>
                      <button type="button" className="btn btn-light ae-comment-private"
                        data-testid={`ae-comment-private-${c.id}`}
                        disabled={busy || privReplyBlocked}
                        title={privReplyBlocked
                          ? 'Réponse privée indisponible (déjà envoyée ou fenêtre de 7 jours dépassée).'
                          : undefined}
                        onClick={() => openReply(c.id, 'private')}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Send size={14} aria-hidden="true" /> Réponse privée
                      </button>
                      <button type="button" className="btn btn-danger-outline ae-comment-delete"
                        data-testid={`ae-comment-delete-${c.id}`} disabled={busy}
                        onClick={() => proposeDelete(c)}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
                        <Trash2 size={14} aria-hidden="true" /> Supprimer
                      </button>
                    </div>

                    {replyingId === c.id && (
                      <div className="ae-comment-reply-panel" data-testid={`ae-comment-reply-panel-${c.id}`}
                        style={{ display: 'flex', gap: '0.4rem', marginTop: '0.5rem', flexWrap: 'wrap' }}>
                        <input type="text" className="form-input ae-comment-reply-input"
                          data-testid={`ae-comment-reply-input-${c.id}`}
                          placeholder={replyMode === 'private' ? 'Message privé (DM)…' : 'Réponse publique…'}
                          value={replyText} onChange={e => setReplyText(e.target.value)}
                          style={{ flex: 1, minWidth: 200 }} />
                        <button type="button" className="btn btn-primary ae-comment-reply-send"
                          data-testid={`ae-comment-reply-send-${c.id}`}
                          disabled={busy || !replyText.trim()}
                          onClick={() => submitReply(c)}>
                          {replyMode === 'private' ? 'Proposer le DM' : 'Proposer la réponse'}
                        </button>
                        <button type="button" className="btn btn-light"
                          onClick={() => setReplyingId(null)}>Annuler</button>
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          )}
    </div>
  )
}
