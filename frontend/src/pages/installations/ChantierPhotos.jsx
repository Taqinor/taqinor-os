// N5 — Photos & fichiers du chantier, groupés avant / pendant / après, avec
// une galerie simple par phase. Réutilise les pièces jointes génériques
// (apps.records, cible installations.installation).
import { useEffect, useRef, useState } from 'react'
import { useSelector } from 'react-redux'
import recordsApi from '../../api/recordsApi'

const PHASES = [
  { key: 'avant', label: 'Avant' },
  { key: 'pendant', label: 'Pendant' },
  { key: 'apres', label: 'Après' },
]

const isImage = (a) => (a.mime ?? '').startsWith('image/')

export default function ChantierPhotos({ installationId }) {
  const isAdmin = useSelector((s) => s.auth.role) === 'admin'
  const [items, setItems] = useState([])
  const [busyPhase, setBusyPhase] = useState(null)
  const fileRefs = { avant: useRef(null), pendant: useRef(null), apres: useRef(null) }

  const load = () => {
    recordsApi.getAttachments('installations.installation', installationId)
      .then((r) => setItems(r.data.results ?? r.data ?? [])).catch(() => {})
  }
  useEffect(() => { load() }, [installationId]) // eslint-disable-line react-hooks/exhaustive-deps

  const upload = async (phase, file) => {
    if (!file) return
    setBusyPhase(phase)
    try {
      await recordsApi.uploadAttachment('installations.installation', installationId, file, phase)
      load()
    } catch { /* erreur silencieuse */ } finally { setBusyPhase(null) }
  }

  const remove = async (att) => {
    if (!window.confirm('Supprimer ce fichier ?')) return
    try { await recordsApi.deleteAttachment(att.id); load() } catch { /* */ }
  }

  // Les pièces sans phase (anciennes / génériques) tombent dans « avant » par défaut.
  const byPhase = (key) => items.filter((a) => (a.phase || 'avant') === key)

  return (
    <div className="form-section">
      <div className="form-section-header">
        <span className="form-section-title">📸 Photos & fichiers</span>
      </div>
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 16 }}>
        {PHASES.map((p) => {
          const atts = byPhase(p.key)
          return (
            <div key={p.key} style={{ flex: '1 1 220px', minWidth: 220 }}>
              <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: 6 }}>
                <strong style={{ fontSize: 13 }}>{p.label} ({atts.length})</strong>
                <input ref={fileRefs[p.key]} type="file" style={{ display: 'none' }}
                       accept="application/pdf,image/png,image/jpeg,image/webp"
                       onChange={(e) => { upload(p.key, e.target.files?.[0]); e.target.value = '' }} />
                <button type="button" className="btn btn-sm btn-outline"
                        disabled={busyPhase === p.key}
                        onClick={() => fileRefs[p.key].current?.click()}>
                  {busyPhase === p.key ? '…' : '＋'}
                </button>
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {atts.length === 0 && <span className="gen-hint">Aucun fichier.</span>}
                {atts.map((a) => (
                  <div key={a.id} style={{ position: 'relative' }}>
                    <a href={a.url} target="_blank" rel="noopener noreferrer" title={a.filename}>
                      {isImage(a) ? (
                        <img src={a.url} alt={a.filename}
                             style={{ width: 64, height: 64, objectFit: 'cover', borderRadius: 6, border: '1px solid #e2e8f0' }} />
                      ) : (
                        <span style={{
                          display: 'inline-flex', alignItems: 'center', justifyContent: 'center',
                          width: 64, height: 64, borderRadius: 6, border: '1px solid #e2e8f0',
                          background: '#f8fafc', fontSize: 22,
                        }}>📄</span>
                      )}
                    </a>
                    {isAdmin && (
                      <button type="button" onClick={() => remove(a)} title="Supprimer"
                              style={{ position: 'absolute', top: -6, right: -6, border: 'none',
                                       background: '#dc2626', color: '#fff', borderRadius: '50%',
                                       width: 18, height: 18, cursor: 'pointer', fontSize: 11, lineHeight: 1 }}>
                        ✕
                      </button>
                    )}
                  </div>
                ))}
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
