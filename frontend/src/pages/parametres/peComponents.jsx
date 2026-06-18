// Briques de présentation partagées de la page Paramètres (D1).
// Extraites telles quelles de ParametresEntreprise.jsx lors de l'éclatement par
// onglet : même rendu, mêmes styles, même comportement.
import { useEffect, useRef, useState } from 'react'
import { ACCEPTED, MAX_MB, inputBase, mediaUrl } from './peConstants'

// ── SVG helper ────────────────────────────────────────────────────────────────
export function Ic({ size = 16, color = 'currentColor', sw = 1.8, children }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" fill="none"
      stroke={color} strokeWidth={sw} strokeLinecap="round" strokeLinejoin="round"
      style={{ flexShrink: 0, display: 'block' }}>
      {children}
    </svg>
  )
}

// ── Section header ────────────────────────────────────────────────────────────
export function SectionTitle({ icon, label, color = '#1d4ed8' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 9, marginBottom: '1.1rem' }}>
      <div style={{
        width: 30, height: 30, borderRadius: 8,
        background: color + '18',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <Ic size={15} color={color} sw={1.8}>{icon}</Ic>
      </div>
      <span style={{ fontSize: 13.5, fontWeight: 700, color: '#1e293b', letterSpacing: '0.01em' }}>
        {label}
      </span>
    </div>
  )
}

// ── Field ─────────────────────────────────────────────────────────────────────
export function Field({ label, required, children }) {
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
      <label style={{ fontSize: 12, fontWeight: 600, color: '#374151' }}>
        {label}{required && <span style={{ color: '#ef4444', marginLeft: 2 }}>*</span>}
      </label>
      {children}
    </div>
  )
}

// ── Image upload zone ─────────────────────────────────────────────────────────
export function UploadZone({ label, hint, currentUrl, onUpload, onDelete, uploading }) {
  const inputRef      = useRef(null)
  const [drag, setDrag] = useState(false)
  const [err,  setErr]  = useState(null)
  const [imgErr, setImgErr] = useState(false)

  const fullUrl = mediaUrl(currentUrl)

  const validate = (file) => {
    if (!ACCEPTED.includes(file.type)) { setErr('Format non supporté (PNG, JPEG, WebP).'); return false }
    if (file.size > MAX_MB * 1024 * 1024) { setErr(`Taille max : ${MAX_MB} Mo.`); return false }
    setErr(null); return true
  }
  const handleFile = (file) => { if (file && validate(file)) { setImgErr(false); onUpload(file) } }
  const handleDrop = (e) => { e.preventDefault(); setDrag(false); handleFile(e.dataTransfer.files[0]) }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>
      <p style={{ margin: 0, fontSize: 12, fontWeight: 600, color: '#374151' }}>{label}</p>

      {/* ── Current image preview ── */}
      {fullUrl && (
        <div style={{ position: 'relative' }}>
          <div style={{
            width: '100%', minHeight: 110, borderRadius: 10,
            border: '1.5px solid #e2e8f0',
            background: 'repeating-linear-gradient(45deg,#f8fafc 0,#f8fafc 8px,#f1f5f9 8px,#f1f5f9 16px)',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            overflow: 'hidden', padding: 10,
          }}>
            {imgErr ? (
              <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 6, color: '#94a3b8' }}>
                <Ic size={28} color="#cbd5e1" sw={1.4}>
                  <rect x="3" y="3" width="18" height="18" rx="2"/>
                  <circle cx="8.5" cy="8.5" r="1.5"/>
                  <polyline points="21 15 16 10 5 21"/>
                </Ic>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>Aperçu indisponible</span>
              </div>
            ) : (
              <img
                src={fullUrl}
                alt={label}
                onError={() => setImgErr(true)}
                style={{
                  maxHeight: 90, maxWidth: '100%',
                  objectFit: 'contain',
                  borderRadius: 6,
                  filter: 'drop-shadow(0 2px 6px rgba(0,0,0,0.12))',
                }}
              />
            )}
          </div>
          {/* Delete button */}
          <button
            type="button" onClick={() => { setImgErr(false); onDelete() }} disabled={uploading}
            style={{
              position: 'absolute', top: -7, right: -7,
              width: 24, height: 24, borderRadius: '50%',
              background: '#ef4444', border: '2px solid #fff',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
              cursor: 'pointer', boxShadow: '0 2px 6px rgba(239,68,68,0.4)',
            }}
            title="Supprimer"
          >
            <Ic size={11} color="#fff" sw={2.5}><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></Ic>
          </button>
        </div>
      )}

      {/* ── Drop zone ── */}
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
        style={{
          border: `1.5px dashed ${drag ? '#1d4ed8' : '#cbd5e1'}`,
          borderRadius: 10, padding: '0.85rem',
          textAlign: 'center', cursor: uploading ? 'default' : 'pointer',
          background: drag ? '#eff6ff' : '#fafafa',
          transition: 'border-color 0.18s, background 0.18s',
        }}
      >
        {uploading ? (
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', gap: 8, color: '#64748b', fontSize: 12.5 }}>
            <div style={{ width: 16, height: 16, border: '2px solid #e2e8f0', borderTopColor: '#1d4ed8', borderRadius: '50%', animation: 'paramSpin 0.7s linear infinite' }}/>
            Téléversement…
          </div>
        ) : (
          <div>
            <Ic size={20} color={drag ? '#1d4ed8' : '#94a3b8'} sw={1.5}>
              <polyline points="16 16 12 12 8 16"/>
              <line x1="12" y1="12" x2="12" y2="21"/>
              <path d="M20.39 18.39A5 5 0 0 0 18 9h-1.26A8 8 0 1 0 3 16.3"/>
            </Ic>
            <p style={{ margin: '5px 0 1px', color: drag ? '#1d4ed8' : '#64748b', fontWeight: 500, fontSize: 12 }}>
              {fullUrl ? 'Remplacer —' : 'Glissez ou'}{' '}
              <span style={{ color: '#1d4ed8', textDecoration: 'underline' }}>parcourez</span>
            </p>
            <span style={{ fontSize: 10.5, color: '#94a3b8' }}>{hint}</span>
          </div>
        )}
      </div>

      <input ref={inputRef} type="file" accept={ACCEPTED.join(',')} style={{ display: 'none' }}
        onChange={e => handleFile(e.target.files[0])}/>
      {err && <p style={{ margin: '2px 0 0', fontSize: 11.5, color: '#ef4444' }}>{err}</p>}
    </div>
  )
}

// ── Référentiel block (Catégories / Fournisseurs) ─────────────────────────────
export function ReferentielBlock({ title, color, icon, items, onCreate, onUpdate, onDelete }) {
  const [newName, setNewName]       = useState('')
  const [creating, setCreating]     = useState(false)
  const [editId, setEditId]         = useState(null)
  const [editName, setEditName]     = useState('')
  const [busy, setBusy]             = useState(false)
  const inputRef = useRef(null)
  const editRef  = useRef(null)

  useEffect(() => { if (creating) inputRef.current?.focus() }, [creating])
  useEffect(() => { if (editId !== null) editRef.current?.focus() }, [editId])

  const doCreate = async () => {
    const nom = newName.trim(); if (!nom) return
    setBusy(true)
    try { await onCreate(nom); setNewName(''); setCreating(false) } catch { /* erreur affichée ailleurs */ } finally { setBusy(false) }
  }

  const doUpdate = async () => {
    const nom = editName.trim(); if (!nom) return
    setBusy(true)
    try { await onUpdate(editId, nom); setEditId(null) } catch { /* erreur affichée ailleurs */ } finally { setBusy(false) }
  }

  const doDelete = async (id) => {
    if (!window.confirm('Supprimer ?')) return
    await onDelete(id)
  }

  return (
    <div style={{ background: '#fff', borderRadius: 14, border: '1px solid #e2e8f0', padding: '1.25rem 1.4rem' }}>
      <SectionTitle color={color} label={title} icon={icon}/>

      <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
        {items.length === 0 && (
          <p style={{ margin: 0, fontSize: 12.5, color: '#94a3b8', fontStyle: 'italic' }}>Aucun élément</p>
        )}
        {items.map(item => (
          <div key={item.id} style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
            {editId === item.id ? (
              <>
                <input
                  ref={editRef}
                  style={{ ...inputBase, flex: 1, padding: '6px 10px', fontSize: 13 }}
                  value={editName}
                  onChange={e => setEditName(e.target.value)}
                  onKeyDown={e => { if (e.key === 'Enter') doUpdate(); if (e.key === 'Escape') setEditId(null) }}
                />
                <button type="button" className="btn btn-primary" disabled={busy || !editName.trim()}
                  onClick={doUpdate} style={{ padding: '5px 10px', fontSize: 12 }}>
                  {busy ? '…' : 'OK'}
                </button>
                <button type="button" className="btn btn-outline"
                  onClick={() => setEditId(null)} style={{ padding: '5px 8px', fontSize: 12 }}>
                  ✕
                </button>
              </>
            ) : (
              <>
                <span style={{ flex: 1, fontSize: 13, color: '#1e293b', padding: '6px 0' }}>{item.nom}</span>
                <button type="button" onClick={() => { setEditId(item.id); setEditName(item.nom) }}
                  title="Renommer" style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px',
                    color: '#64748b', borderRadius: 6, lineHeight: 1,
                  }}>
                  <Ic size={13} color="#64748b" sw={2}><path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/><path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/></Ic>
                </button>
                <button type="button" onClick={() => doDelete(item.id)}
                  title="Supprimer" style={{
                    background: 'none', border: 'none', cursor: 'pointer', padding: '4px 6px',
                    color: '#ef4444', borderRadius: 6, lineHeight: 1,
                  }}>
                  <Ic size={13} color="#ef4444" sw={2}><polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6"/><path d="M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/></Ic>
                </button>
              </>
            )}
          </div>
        ))}
      </div>

      {creating ? (
        <div style={{ display: 'flex', gap: 6 }}>
          <input
            ref={inputRef}
            style={{ ...inputBase, flex: 1, padding: '7px 10px', fontSize: 13 }}
            value={newName}
            onChange={e => setNewName(e.target.value)}
            onKeyDown={e => { if (e.key === 'Enter') doCreate(); if (e.key === 'Escape') { setCreating(false); setNewName('') } }}
            placeholder="Nouveau nom…"
          />
          <button type="button" className="btn btn-primary" disabled={busy || !newName.trim()}
            onClick={doCreate} style={{ padding: '6px 12px', fontSize: 13 }}>
            {busy ? '…' : 'Ajouter'}
          </button>
          <button type="button" className="btn btn-outline"
            onClick={() => { setCreating(false); setNewName('') }} style={{ padding: '6px 10px', fontSize: 13 }}>
            ✕
          </button>
        </div>
      ) : (
        <button type="button" onClick={() => setCreating(true)} style={{
          display: 'inline-flex', alignItems: 'center', gap: 5,
          padding: '6px 12px', borderRadius: 8, border: `1.5px dashed ${color}60`,
          background: color + '08', color, fontSize: 12.5, fontWeight: 600, cursor: 'pointer',
        }}>
          <Ic size={13} color={color} sw={2.5}><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></Ic>
          Ajouter
        </button>
      )}
    </div>
  )
}
