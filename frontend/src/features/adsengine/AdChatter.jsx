import { useState, useEffect, useCallback } from 'react'
import { MessageSquarePlus } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB55 — Chatter d'entité RÉUTILISABLE (campagne / ad set / ad).
   ----------------------------------------------------------------------------
   Un fil chronologique UNIQUE mêlant les événements AUTO (actions appliquées,
   alertes — déjà persistés, fusionnés côté serveur) et les notes MANUELLES
   (acteur + société posés côté serveur). Embarqué sur la fiche ad (PUB44) et le
   détail campagne. Rendu lecture + une zone de saisie de note.
   ========================================================================== */

const KIND_LABEL = {
  note: 'Note', action_applied: 'Action appliquée', alert: 'Alerte',
}

export default function AdChatter({ entityType, entityId }) {
  const [items, setItems] = useState([])
  const [draft, setDraft] = useState('')
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const [err, setErr] = useState('')

  const load = useCallback(() => {
    if (!entityType || !entityId) { setLoading(false); return }
    setLoading(true)
    adsengineApi.chatter.timeline(entityType, entityId)
      .then(r => setItems(Array.isArray(r.data) ? r.data : []))
      .catch(() => setErr('Chargement du fil impossible.'))
      .finally(() => setLoading(false))
  }, [entityType, entityId])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage / changement d'entité
  useEffect(() => { load() }, [load])

  const postNote = async (e) => {
    e.preventDefault()
    if (!draft.trim()) return
    setBusy(true); setErr('')
    try {
      await adsengineApi.chatter.postNote(entityType, entityId, draft.trim())
      setDraft('')
      load()
    } catch {
      setErr('Publication de la note impossible.')
    } finally {
      setBusy(false)
    }
  }

  return (
    <div className="ae-chatter" data-testid="ae-chatter">
      <h3 className="h6">Fil d'activité</h3>
      {err && <div className="alert alert-danger" data-testid="ae-chatter-err">{err}</div>}

      <form onSubmit={postNote} data-testid="ae-chatter-form" className="d-flex gap-2 mb-3">
        <input
          className="form-control" data-testid="ae-chatter-input"
          value={draft} onChange={e => setDraft(e.target.value)}
          placeholder="Ajouter une note…" />
        <button
          type="submit" className="btn btn-primary"
          data-testid="ae-chatter-submit" disabled={busy || !draft.trim()}>
          <MessageSquarePlus size={15} aria-hidden="true" /> Noter
        </button>
      </form>

      {loading ? (
        <p data-testid="ae-chatter-loading">Chargement…</p>
      ) : items.length === 0 ? (
        <p className="text-muted" data-testid="ae-chatter-empty">Aucune activité.</p>
      ) : (
        <ul className="list-unstyled" data-testid="ae-chatter-list">
          {items.map((it, idx) => (
            <li key={idx} data-testid={`ae-chatter-item-${idx}`}
              className={`ae-chatter-${it.kind} border-start ps-2 mb-2`}>
              <span className="badge bg-light text-dark me-2">
                {KIND_LABEL[it.kind] || it.kind}
              </span>
              <span>{it.body}</span>
              <div className="text-muted small">
                {it.author ? `${it.author} · ` : ''}{(it.at || '').slice(0, 10)}
              </div>
            </li>
          ))}
        </ul>
      )}
    </div>
  )
}
