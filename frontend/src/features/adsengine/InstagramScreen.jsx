import { useEffect, useState, useCallback } from 'react'
import {
  Camera, Send, Lock, Heart, MessageCircle, Eye, EyeOff, Reply, Trash2,
  MessagesSquare, Clock,
} from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   ADSDEEP56 — Écran Instagram (compte Business relié).
   ----------------------------------------------------------------------------
   Grille de médias + métriques, composeur de PUBLICATION (image / Reel,
   programmable) et gestion des COMMENTAIRES IG (repris de la boîte de réception
   ADSDEEP54). Doctrine règle #3 : publier / masquer / répondre / supprimer /
   couper les commentaires ne fait que PROPOSER une `EngineAction` — l'application
   passe par la boîte d'approbation. La LÉGENDE est LECTURE SEULE : Meta ne permet
   pas de l'éditer après publication (l'UI le dit, et le composeur avertit que la
   légende sera définitive). Le quota (50 publications / 24 h) est affiché.
   ========================================================================== */

const MEDIA_TYPES = [
  { value: 'IMAGE', label: 'Image (JPEG)' },
  { value: 'REELS', label: 'Reel (MP4 H.264, ≤ 300 Mo, 9:16)' },
]

export default function InstagramScreen() {
  const [media, setMedia] = useState([])
  const [comments, setComments] = useState([])
  const [quota, setQuota] = useState(null)
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  const [proposed, setProposed] = useState(() => new Set())
  const [busy, setBusy] = useState(false)

  // Composeur de publication.
  const [showComposer, setShowComposer] = useState(false)
  const [mediaType, setMediaType] = useState('IMAGE')
  const [mediaUrl, setMediaUrl] = useState('')
  const [caption, setCaption] = useState('')
  const [scheduledAt, setScheduledAt] = useState('')
  const [composerMsg, setComposerMsg] = useState('')

  // Réponse à un commentaire IG.
  const [replyingId, setReplyingId] = useState(null)
  const [replyText, setReplyText] = useState('')

  const load = useCallback(() => {
    setLoading(true)
    Promise.all([
      adsengineApi.instagram.media().then(r => r.data).catch(() => []),
      adsengineApi.instagram.comments().then(r => r.data).catch(() => []),
      adsengineApi.instagram.quota().then(r => r.data).catch(() => null),
    ]).then(([m, c, q]) => {
      setMedia(Array.isArray(m) ? m : (m?.results || []))
      setComments(Array.isArray(c) ? c : (c?.results || []))
      setQuota(q && typeof q === 'object' ? q : null)
    }).finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  const markProposed = (key) => setProposed(s => new Set(s).add(key))

  const runAction = async (fn, key) => {
    setBusy(true); setErr('')
    try {
      await fn()
      markProposed(key)
      setReplyingId(null); setReplyText('')
    } catch {
      setErr("Action impossible (permission ?). Rien n'a été proposé.")
    } finally {
      setBusy(false)
    }
  }

  const submitPublish = async () => {
    if (!mediaUrl.trim()) return
    const payload = {
      media_type: mediaType,
      image_url: mediaType === 'IMAGE' ? mediaUrl.trim() : '',
      video_url: mediaType === 'REELS' ? mediaUrl.trim() : '',
      caption,
      scheduled_at: scheduledAt || null,
    }
    setBusy(true); setErr(''); setComposerMsg('')
    try {
      await adsengineApi.instagram.proposePublish(payload)
      setComposerMsg('Publication proposée — à approuver dans la boîte d’approbation.')
      setMediaUrl(''); setCaption(''); setScheduledAt('')
    } catch {
      setErr("Publication impossible (permission ?). Rien n'a été proposé.")
    } finally {
      setBusy(false)
    }
  }

  const commentsFor = (mediaId) =>
    comments.filter(c => (c.media_meta_id || '') === mediaId)

  const proposeHide = (c) =>
    runAction(() => adsengineApi.instagram.proposeHideComment(c.id, { hidden: !c.hidden }), `c-${c.id}`)
  const proposeDelete = (c) =>
    runAction(() => adsengineApi.instagram.proposeDeleteComment(c.id), `c-${c.id}`)
  const submitReply = (c) => {
    const text = replyText.trim()
    if (!text) return
    return runAction(() => adsengineApi.instagram.proposeReplyComment(c.id, { message: text }), `c-${c.id}`)
  }
  const proposeToggle = (m) =>
    runAction(() => adsengineApi.instagram.proposeToggleComments(m.meta_id, { enabled: !m.comment_enabled }), `m-${m.id}`)

  return (
    <div className="page ae-instagram">
      <div className="page-header" style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '0.4rem' }}>
          <Camera size={20} aria-hidden="true" /> Instagram
        </h2>
        <button type="button" className="btn btn-light ae-ig-toggle-composer"
          data-testid="ae-ig-toggle-composer"
          onClick={() => setShowComposer(v => !v)}
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
          <Send size={15} aria-hidden="true" />
          {showComposer ? 'Fermer le composeur' : 'Publier un média'}
        </button>
      </div>

      {/* Quota 50/24 h */}
      {quota && (
        <div className="ae-ig-quota" data-testid="ae-ig-quota"
          style={{ display: 'inline-flex', alignItems: 'center', gap: '0.4rem',
            background: '#eef2ff', color: '#3730a3', borderRadius: 8, padding: '0.4rem 0.75rem', margin: '0 0 1rem', fontSize: '0.85rem' }}>
          <Clock size={14} aria-hidden="true" />
          Quota de publication : {quota.used ?? '?'}/{quota.total ?? 50} sur 24 h
          {typeof quota.remaining === 'number' && ` · ${quota.remaining} restante(s)`}
        </div>
      )}

      {err && <p data-testid="ae-ig-err" style={{ color: '#dc2626' }}>{err}</p>}

      {/* Composeur de publication */}
      {showComposer && (
        <div className="card ae-ig-composer" data-testid="ae-ig-composer"
          style={{ padding: '1rem', border: '1px solid #e2e8f0', margin: '0 0 1.25rem', display: 'grid', gap: '0.6rem' }}>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>Type de média</span>
            <select className="form-input ae-ig-type" data-testid="ae-ig-type"
              value={mediaType} onChange={e => setMediaType(e.target.value)}>
              {MEDIA_TYPES.map(t => <option key={t.value} value={t.value}>{t.label}</option>)}
            </select>
          </label>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>
              {mediaType === 'REELS' ? 'URL de la vidéo (Reel)' : "URL de l'image (JPEG)"}
            </span>
            <input type="text" className="form-input ae-ig-url" data-testid="ae-ig-url"
              value={mediaUrl} onChange={e => setMediaUrl(e.target.value)}
              placeholder="https://…" />
          </label>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>Légende</span>
            <textarea className="form-input ae-ig-caption" data-testid="ae-ig-caption"
              value={caption} onChange={e => setCaption(e.target.value)} rows={3} />
          </label>
          {/* Avertissement légende immuable */}
          <p className="ae-ig-caption-warning" data-testid="ae-ig-caption-warning"
            style={{ display: 'flex', alignItems: 'center', gap: '0.35rem', margin: 0,
              color: '#9a3412', background: '#fff7ed', border: '1px solid #fed7aa', borderRadius: 6, padding: '0.4rem 0.6rem', fontSize: '0.8rem' }}>
            <Lock size={13} aria-hidden="true" />
            La légende ne pourra PLUS être modifiée après publication — vérifiez-la, c’est définitif.
          </p>
          <label style={{ display: 'grid', gap: '0.25rem' }}>
            <span style={{ fontSize: '0.85rem', color: '#475569' }}>Programmer (optionnel)</span>
            <input type="datetime-local" className="form-input ae-ig-scheduled" data-testid="ae-ig-scheduled"
              value={scheduledAt} onChange={e => setScheduledAt(e.target.value)} />
          </label>
          <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
            <button type="button" className="btn btn-primary ae-ig-publish" data-testid="ae-ig-publish"
              disabled={busy || !mediaUrl.trim()} onClick={submitPublish}>
              Proposer la publication
            </button>
            {composerMsg && (
              <span data-testid="ae-ig-composer-msg" style={{ color: '#7c3aed', fontSize: '0.85rem' }}>
                {composerMsg}
              </span>
            )}
          </div>
        </div>
      )}

      {loading
        ? <p className="page-loading">Chargement…</p>
        : media.length === 0
          ? <p data-testid="ae-ig-empty" style={{ color: '#64748b' }}>Aucun média Instagram.</p>
          : (
            <div className="ae-ig-grid" data-testid="ae-ig-grid"
              style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '1rem' }}>
              {media.map(m => {
                const mComments = commentsFor(m.meta_id)
                return (
                  <article key={m.id} className="card ae-ig-media-card" data-testid="ae-ig-media-card"
                    style={{ padding: '0.85rem', border: '1px solid #e2e8f0', display: 'grid', gap: '0.5rem' }}>
                    {m.media_url
                      ? <img src={m.media_url} alt={m.caption || 'Média Instagram'}
                          style={{ width: '100%', maxHeight: 200, objectFit: 'cover', borderRadius: 6 }} />
                      : <div style={{ padding: '1.5rem', background: '#f1f5f9', borderRadius: 6, color: '#64748b', textAlign: 'center' }}>
                          {m.media_type || 'Média'}
                        </div>}

                    {/* Légende LECTURE SEULE */}
                    <div>
                      <span data-testid={`ae-ig-caption-readonly-${m.id}`}
                        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', color: '#94a3b8', fontSize: '0.72rem' }}>
                        <Lock size={11} aria-hidden="true" /> Légende — lecture seule
                      </span>
                      <p style={{ margin: '0.2rem 0', color: '#334155', fontSize: '0.9rem' }}>
                        {m.caption || <em style={{ color: '#94a3b8' }}>(sans légende)</em>}
                      </p>
                    </div>

                    {/* Métriques */}
                    <div style={{ display: 'flex', gap: '0.9rem', color: '#475569', fontSize: '0.8rem' }}>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <Heart size={13} aria-hidden="true" /> {m.like_count ?? 0}
                      </span>
                      <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                        <MessageCircle size={13} aria-hidden="true" /> {m.comments_count ?? 0}
                      </span>
                      {(m.media_type === 'VIDEO' || m.media_type === 'REELS') && (
                        <span style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                          <Eye size={13} aria-hidden="true" /> {m.view_count ?? 0}
                        </span>
                      )}
                    </div>

                    <button type="button" className="btn btn-light ae-ig-toggle-comments"
                      data-testid={`ae-ig-toggle-comments-${m.id}`} disabled={busy}
                      onClick={() => proposeToggle(m)}
                      style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem', fontSize: '0.8rem' }}>
                      <MessagesSquare size={13} aria-hidden="true" />
                      {m.comment_enabled ? 'Couper les commentaires' : 'Rouvrir les commentaires'}
                    </button>
                    {proposed.has(`m-${m.id}`) && (
                      <span data-testid={`ae-ig-proposed-m-${m.id}`} style={{ color: '#7c3aed', fontSize: '0.78rem' }}>
                        Proposé — à approuver.
                      </span>
                    )}

                    {/* Commentaires IG (repris de la boîte de réception ADSDEEP54) */}
                    {mComments.length > 0 && (
                      <div className="ae-ig-comments" data-testid={`ae-ig-comments-${m.id}`}
                        style={{ display: 'grid', gap: '0.4rem', borderTop: '1px solid #f1f5f9', paddingTop: '0.5rem' }}>
                        {mComments.map(c => (
                          <div key={c.id} className="ae-ig-comment" data-testid="ae-ig-comment"
                            style={{ fontSize: '0.82rem', opacity: c.hidden ? 0.6 : 1 }}>
                            <strong>{c.from_username || 'Anonyme'}</strong>{' '}
                            <span style={{ color: '#334155' }}>{c.message}</span>
                            <div style={{ display: 'flex', gap: '0.35rem', marginTop: '0.2rem', flexWrap: 'wrap' }}>
                              <button type="button" className="btn btn-light ae-ig-comment-hide"
                                data-testid={`ae-ig-comment-hide-${c.id}`} disabled={busy}
                                onClick={() => proposeHide(c)}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem' }}>
                                {c.hidden ? <><Eye size={12} aria-hidden="true" /> Démasquer</> : <><EyeOff size={12} aria-hidden="true" /> Masquer</>}
                              </button>
                              <button type="button" className="btn btn-light ae-ig-comment-reply"
                                data-testid={`ae-ig-comment-reply-${c.id}`} disabled={busy}
                                onClick={() => { setReplyingId(c.id); setReplyText('') }}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem' }}>
                                <Reply size={12} aria-hidden="true" /> Répondre
                              </button>
                              <button type="button" className="btn btn-danger-outline ae-ig-comment-delete"
                                data-testid={`ae-ig-comment-delete-${c.id}`} disabled={busy}
                                onClick={() => proposeDelete(c)}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem', fontSize: '0.75rem' }}>
                                <Trash2 size={12} aria-hidden="true" /> Supprimer
                              </button>
                            </div>
                            {replyingId === c.id && (
                              <div data-testid={`ae-ig-reply-panel-${c.id}`}
                                style={{ display: 'flex', gap: '0.35rem', marginTop: '0.3rem', flexWrap: 'wrap' }}>
                                <input type="text" className="form-input"
                                  data-testid={`ae-ig-reply-input-${c.id}`}
                                  value={replyText} onChange={e => setReplyText(e.target.value)}
                                  placeholder="Réponse…" style={{ flex: 1, minWidth: 160 }} />
                                <button type="button" className="btn btn-primary"
                                  data-testid={`ae-ig-reply-send-${c.id}`}
                                  disabled={busy || !replyText.trim()} onClick={() => submitReply(c)}>
                                  Proposer
                                </button>
                              </div>
                            )}
                            {proposed.has(`c-${c.id}`) && (
                              <span data-testid={`ae-ig-proposed-c-${c.id}`} style={{ color: '#7c3aed', fontSize: '0.72rem' }}>
                                Proposé — à approuver.
                              </span>
                            )}
                          </div>
                        ))}
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
