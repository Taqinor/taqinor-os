/**
 * FG7 — ChatterWidget
 * Composant chatter générique : liste les commentaires d'un enregistrement,
 * permet d'en ajouter/supprimer. Supporte les @mentions (highlighting visuel).
 *
 * Props:
 *   model  — ex. 'crm.lead'
 *   id     — PK de l'enregistrement
 *   readOnly (bool, défaut false)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import { MessageSquare, Send, Trash2 } from 'lucide-react'
import recordsApi from '../api/recordsApi'
import { IconButton } from '../ui/IconButton'

// Surligne les @mentions dans le texte.
function renderBody(body) {
  if (!body) return null
  const parts = body.split(/(@\w+)/g)
  return parts.map((part, i) =>
    /^@\w+$/.test(part)
      ? <span key={i} className="mention">@{part.slice(1)}</span>
      : part
  )
}

function formatDate(iso) {
  if (!iso) return ''
  try {
    return new Intl.DateTimeFormat('fr-FR', {
      day: '2-digit', month: '2-digit', year: 'numeric',
      hour: '2-digit', minute: '2-digit',
    }).format(new Date(iso))
  } catch {
    return iso
  }
}

export default function ChatterWidget({ model, id, readOnly = false }) {
  const user = useSelector((s) => s.auth?.user)
  const [comments, setComments] = useState([])
  const [body, setBody] = useState('')
  const [loading, setLoading] = useState(false)
  const [submitting, setSubmitting] = useState(false)
  // VX204 — un échec de chargement/envoi ne doit jamais rendre un état muet
  // (liste vide indiscernable d'« aucun commentaire »).
  const [loadError, setLoadError] = useState(false)
  const [submitError, setSubmitError] = useState(false)
  const textareaRef = useRef(null)

  const load = useCallback(async () => {
    if (!model || !id) return
    setLoading(true)
    try {
      const res = await recordsApi.getComments(model, id)
      const data = res.data
      setComments(Array.isArray(data)
        ? data
        : (data?.results ?? []))
      setLoadError(false)
    } catch {
      setLoadError(true)
    } finally {
      setLoading(false)
    }
  }, [model, id])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount
  useEffect(() => { load() }, [load])

  async function handleSubmit(e) {
    e.preventDefault()
    const text = body.trim()
    if (!text || submitting) return
    setSubmitting(true)
    setSubmitError(false)
    try {
      const res = await recordsApi.createComment(model, id, text)
      setComments(prev => [...prev, res.data])
      setBody('')
    } catch {
      setSubmitError(true)
    } finally {
      setSubmitting(false)
    }
  }

  async function handleDelete(commentId) {
    try {
      await recordsApi.deleteComment(commentId)
      setComments(prev => prev.filter(c => c.id !== commentId))
    } catch {
      setSubmitError(true)
    }
  }

  const isAdmin = user?.role === 'admin' || user?.is_superuser

  return (
    <div className="chatter-widget">
      <div className="chatter-header">
        <MessageSquare size={16} />
        <span>Commentaires {comments.length > 0 && `(${comments.length})`}</span>
      </div>

      <div className="chatter-list" role="log" aria-live="polite" aria-relevant="additions">
        {loading && (
          <div className="chatter-empty">Chargement…</div>
        )}
        {!loading && loadError && (
          <div className="chatter-empty chatter-error" role="alert">
            Impossible de charger les commentaires.
            <button type="button" className="chatter-retry" onClick={load}>Réessayer</button>
          </div>
        )}
        {!loading && !loadError && comments.length === 0 && (
          <div className="chatter-empty">Aucun commentaire.</div>
        )}
        {comments.map(c => (
          <div key={c.id} className="chatter-item">
            <div className="chatter-meta">
              <span className="chatter-author">{c.author_display || c.author_username || 'Système'}</span>
              <span className="chatter-date">{formatDate(c.created_at)}</span>
              {/* Suppression : auteur lui-même ou admin */}
              {!readOnly && (user?.username === c.author_username || isAdmin) && (
                // VX194(b) — WCAG 2.5.8 : ce bouton (Trash2 size=12, aucun CSS
                // dédié) était largement sous 24×24 px hors `pointer: coarse`.
                // `IconButton size="icon-sm"` pose le plancher AA sans faire
                // grossir la ligne de métadonnées comme le ferait `icon`
                // (~40px, --control-h).
                <IconButton
                  className="chatter-delete"
                  variant="ghost"
                  size="icon-sm"
                  title="Supprimer"
                  label="Supprimer le commentaire"
                  onClick={() => handleDelete(c.id)}
                >
                  <Trash2 size={14} />
                </IconButton>
              )}
            </div>
            <div className="chatter-body">{renderBody(c.body)}</div>
          </div>
        ))}
      </div>

      {!readOnly && submitError && (
        <p className="form-error" role="alert">Envoi impossible — réessayez.</p>
      )}

      {!readOnly && (
        <form className="chatter-form" onSubmit={handleSubmit}>
          <textarea
            ref={textareaRef}
            className="chatter-textarea"
            placeholder="Ajouter un commentaire… (@mention pour notifier)"
            value={body}
            onChange={e => setBody(e.target.value)}
            rows={2}
            onKeyDown={e => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) handleSubmit(e)
            }}
          />
          <button
            type="submit"
            className="chatter-submit"
            disabled={!body.trim() || submitting}
            title="Envoyer (Ctrl+Entrée)"
          >
            <Send size={14} />
          </button>
        </form>
      )}
    </div>
  )
}
