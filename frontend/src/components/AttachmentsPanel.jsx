/* Pièces jointes (style Odoo) pour n'importe quel enregistrement.
   Réutilisable : model ('crm.lead'…) + id. Ajout = Commerciale ; suppression
   = admin (le backend l'impose ; on masque le bouton pour les autres). */
import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import recordsApi from '../api/recordsApi'

const fmtSize = (n) => {
  if (!n) return ''
  if (n < 1024) return `${n} o`
  if (n < 1024 * 1024) return `${Math.round(n / 1024)} Ko`
  return `${(n / 1024 / 1024).toFixed(1)} Mo`
}

export default function AttachmentsPanel({ model, id, onChange }) {
  const role = useSelector(s => s.auth.role)
  const isAdmin = role === 'admin'
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const fileRef = useRef(null)

  const load = () => {
    recordsApi.getAttachments(model, id)
      .then(r => setItems(r.data.results ?? r.data)).catch(() => {})
  }
  useEffect(() => { load() }, [model, id]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return
    setBusy(true); setError(null)
    try {
      await recordsApi.uploadAttachment(model, id, file)
      load(); onChange?.()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'envoi.")
    } finally { setBusy(false) }
  }

  const remove = async (att) => {
    if (!window.confirm('Supprimer cette pièce jointe ?')) return
    try { await recordsApi.deleteAttachment(att.id); load(); onChange?.() } catch { /* */ }
  }

  return (
    <div className="att-panel">
      <div className="act-head">
        <span className="act-count">📎 {items.length} pièce(s) jointe(s)</span>
        <input ref={fileRef} type="file" style={{ display: 'none' }}
               accept="application/pdf,image/png,image/jpeg,image/webp"
               onChange={e => { upload(e.target.files?.[0]); e.target.value = '' }} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy}
                onClick={() => fileRef.current?.click()}>
          {busy ? 'Envoi…' : '＋ Ajouter un fichier'}
        </button>
      </div>
      {error && <div className="form-error-box" role="alert">{error}</div>}
      <div className="att-list">
        {items.length === 0 && <p className="gen-hint">Aucune pièce jointe.</p>}
        {items.map(a => (
          <div key={a.id} className="att-item">
            <a href={a.url} target="_blank" rel="noopener noreferrer" className="att-name">
              📄 {a.filename}
            </a>
            <span className="att-meta">
              {fmtSize(a.size)}{a.uploaded_by_nom ? ` · ${a.uploaded_by_nom}` : ''}
              {a.created_at ? ` · ${new Date(a.created_at).toLocaleDateString('fr-FR')}` : ''}
            </span>
            {isAdmin && (
              <button type="button" className="btn-icon-danger" title="Supprimer"
                      onClick={() => remove(a)}>✕</button>
            )}
          </div>
        ))}
      </div>
    </div>
  )
}
