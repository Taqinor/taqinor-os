/**
 * FG9 — TagChipInput
 * Composant chip-input pour appliquer/retirer des tags sur un enregistrement.
 *
 * Props:
 *   model  — ex. 'crm.lead'
 *   id     — PK de l'enregistrement
 *   readOnly (bool, défaut false)
 */
import { useCallback, useEffect, useRef, useState } from 'react'
import { Tag as TagIcon, X } from 'lucide-react'
import recordsApi from '../api/recordsApi'

function Chip({ tag, onRemove, readOnly }) {
  const bg = tag.tag_couleur || tag.couleur || '#e2e8f0'
  return (
    <span className="tag-chip" style={{ background: bg + '22', borderColor: bg }}>
      <span style={{ color: bg || '#475569' }}>{tag.tag_nom || tag.nom}</span>
      {!readOnly && onRemove && (
        <button
          className="tag-chip-remove"
          title="Retirer le tag"
          onClick={() => onRemove(tag)}
        >
          <X size={10} />
        </button>
      )}
    </span>
  )
}

export default function TagChipInput({ model, id, readOnly = false }) {
  const [applied, setApplied] = useState([])   // TaggedItem[]
  const [vocab, setVocab] = useState([])        // Tag[] (vocabulaire société)
  const [search, setSearch] = useState('')
  const [open, setOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const inputRef = useRef(null)

  const loadApplied = useCallback(async () => {
    if (!model || !id) return
    try {
      const res = await recordsApi.getTaggedItems(model, id)
      const data = res.data
      setApplied(Array.isArray(data) ? data : (data?.results ?? []))
    } catch { /* ignore */ }
  }, [model, id])

  const loadVocab = useCallback(async (q) => {
    try {
      const res = await recordsApi.getTags(q)
      const data = res.data
      setVocab(Array.isArray(data) ? data : (data?.results ?? []))
    } catch { /* ignore */ }
  }, [])

  useEffect(() => { loadApplied() }, [loadApplied])
  useEffect(() => { if (open) loadVocab(search) }, [open, search, loadVocab])

  async function handleAdd(tag) {
    try {
      const res = await recordsApi.addTag(model, id, tag.id)
      setApplied(prev => {
        const exists = prev.some(t => t.tag === tag.id)
        if (exists) return prev
        return [...prev, res.data]
      })
    } catch { /* ignore */ }
    setSearch('')
    setOpen(false)
  }

  async function handleRemove(taggedItem) {
    try {
      await recordsApi.removeTag(taggedItem.id)
      setApplied(prev => prev.filter(t => t.id !== taggedItem.id))
    } catch { /* ignore */ }
  }

  async function handleCreate() {
    if (!search.trim()) return
    setCreating(true)
    try {
      const res = await recordsApi.createTag(search.trim())
      const newTag = res.data
      await handleAdd(newTag)
      await loadVocab('')
    } catch { /* ignore */ }
    setCreating(false)
    setSearch('')
  }

  const appliedTagIds = new Set(applied.map(t => t.tag))
  const filtered = vocab.filter(
    t => !appliedTagIds.has(t.id) && t.nom.toLowerCase().includes(search.toLowerCase())
  )
  const exactMatch = vocab.some(t => t.nom.toLowerCase() === search.toLowerCase().trim())

  return (
    <div className="tag-chip-input">
      <div className="tag-chip-header">
        <TagIcon size={13} />
        <span>Tags</span>
      </div>
      <div className="tag-chip-area">
        {applied.map(t => (
          <Chip key={t.id} tag={t} onRemove={!readOnly ? handleRemove : null} readOnly={readOnly} />
        ))}
        {!readOnly && (
          <div className="tag-chip-input-wrap" ref={inputRef}>
            <input
              className="tag-chip-search"
              placeholder="Ajouter un tag…"
              value={search}
              onChange={e => { setSearch(e.target.value); setOpen(true) }}
              onFocus={() => setOpen(true)}
              onBlur={() => setTimeout(() => setOpen(false), 150)}
              onKeyDown={e => {
                if (e.key === 'Enter' && !exactMatch && search.trim()) handleCreate()
              }}
            />
            {open && (
              <div className="tag-chip-dropdown">
                {filtered.map(t => (
                  <button
                    key={t.id}
                    className="tag-chip-option"
                    onMouseDown={e => { e.preventDefault(); handleAdd(t) }}
                  >
                    {t.couleur && (
                      <span
                        className="tag-chip-dot"
                        style={{ background: t.couleur }}
                      />
                    )}
                    {t.nom}
                  </button>
                ))}
                {!exactMatch && search.trim() && (
                  <button
                    className="tag-chip-option tag-chip-create"
                    onMouseDown={e => { e.preventDefault(); handleCreate() }}
                    disabled={creating}
                  >
                    Créer « {search.trim()} »
                  </button>
                )}
                {filtered.length === 0 && !search.trim() && (
                  <div className="tag-chip-empty">Aucun tag. Tapez pour créer.</div>
                )}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}
