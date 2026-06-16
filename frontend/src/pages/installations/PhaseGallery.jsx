// Galerie photos/fichiers d'un chantier groupée par phase (N4) : Avant /
// Pendant / Après (+ « Autres » pour les non taguées). Upload taggé par phase
// et re-tag d'une pièce existante. Réutilise records.Attachment (MinIO).
import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import recordsApi from '../../api/recordsApi'

const MODEL = 'installations.installation'

const PHASES = [
  { key: 'avant', label: 'Avant' },
  { key: 'pendant', label: 'Pendant' },
  { key: 'apres', label: 'Après' },
]
const PHASE_OPTIONS = [...PHASES, { key: '', label: 'Autres' }]

const isImage = (mime) => typeof mime === 'string' && mime.startsWith('image/')

export default function PhaseGallery({ installationId, onChange }) {
  const role = useSelector(s => s.auth.role)
  const isAdmin = role === 'admin'
  const [items, setItems] = useState([])
  const [busy, setBusy] = useState(false)
  const [error, setError] = useState(null)
  const [uploadPhase, setUploadPhase] = useState('avant')
  const fileRef = useRef(null)

  const load = () => {
    recordsApi.getAttachments(MODEL, installationId)
      .then(r => setItems(r.data.results ?? r.data ?? [])).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (file) => {
    if (!file) return
    setBusy(true); setError(null)
    try {
      await recordsApi.uploadAttachment(MODEL, installationId, file,
        uploadPhase || undefined)
      load(); onChange?.()
    } catch (err) {
      setError(err.response?.data?.detail ?? "Échec de l'envoi.")
    } finally { setBusy(false) }
  }

  const retag = async (att, phase) => {
    try {
      await recordsApi.setAttachmentPhase(att.id, phase || null)
      load()
    } catch { /* erreur silencieuse */ }
  }

  const remove = async (att) => {
    if (!window.confirm('Supprimer cette pièce jointe ?')) return
    try { await recordsApi.deleteAttachment(att.id); load(); onChange?.() } catch { /* */ }
  }

  const groups = PHASE_OPTIONS.map(p => ({
    ...p,
    files: items.filter(a => (a.phase ?? '') === p.key),
  })).filter(g => g.files.length > 0 || g.key !== '')

  return (
    <div>
      <div className="cd-upload-row">
        <label className="form-label" style={{ margin: 0 }}>Phase :</label>
        <select className="form-select" style={{ width: 'auto' }}
                value={uploadPhase}
                onChange={e => setUploadPhase(e.target.value)}>
          {PHASE_OPTIONS.map(p => (
            <option key={p.key} value={p.key}>{p.label}</option>
          ))}
        </select>
        <input ref={fileRef} type="file" style={{ display: 'none' }}
               accept="application/pdf,image/png,image/jpeg,image/webp"
               onChange={e => { upload(e.target.files?.[0]); e.target.value = '' }} />
        <button type="button" className="btn btn-sm btn-primary" disabled={busy}
                onClick={() => fileRef.current?.click()}>
          {busy ? 'Envoi…' : '＋ Ajouter une photo'}
        </button>
      </div>
      {error && <div className="form-error-box" role="alert">{error}</div>}

      {items.length === 0 && <p className="gen-hint">Aucune photo pour ce chantier.</p>}

      {groups.map(group => (
        <div key={group.key || 'autres'} className="cd-phase-group">
          <div className="cd-phase-title">{group.label} ({group.files.length})</div>
          {group.files.length === 0 ? (
            <p className="gen-hint">Aucune pièce dans cette phase.</p>
          ) : (
            <div className="cd-gallery">
              {group.files.map(att => (
                <div key={att.id} className="cd-thumb">
                  {isImage(att.mime) ? (
                    <a href={att.url} target="_blank" rel="noopener noreferrer"
                       className="cd-thumb-img" title={att.filename}>
                      <img src={att.url} alt={att.filename} />
                    </a>
                  ) : (
                    <a href={att.url} target="_blank" rel="noopener noreferrer"
                       className="cd-thumb-file" title={att.filename}>
                      📄 {att.filename}
                    </a>
                  )}
                  <select className="cd-thumb-phase" value={att.phase ?? ''}
                          onChange={e => retag(att, e.target.value)}>
                    {PHASE_OPTIONS.map(p => (
                      <option key={p.key} value={p.key}>{p.label}</option>
                    ))}
                  </select>
                  {isAdmin && (
                    <button type="button" className="btn-icon-danger"
                            title="Supprimer" onClick={() => remove(att)}>✕</button>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>
      ))}
    </div>
  )
}
