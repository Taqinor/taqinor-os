// Briques de présentation partagées de la page Paramètres (D1).
// Restylées sur le système de design (@/ui — Groupe G) tout en conservant
// EXACTEMENT le même rendu fonctionnel, les mêmes libellés et le même
// comportement (J48). Aucun réglage, aucun appel API n'est ajouté ni retiré.
import { useEffect, useRef, useState } from 'react'
import { Trash2, Pencil, Plus, X, ImageOff, UploadCloud } from 'lucide-react'
import {
  Card, CardContent, Label, Input, Button, IconButton, Spinner, EmptyState,
} from '../../ui'
import { ACCEPTED, MAX_MB, mediaUrl } from './peConstants'

// ── SVG helper ────────────────────────────────────────────────────────────────
// Conservé : les icônes de titre de section sont passées en tracés SVG bruts
// par chaque section. Couleur héritée (currentColor) → suit les tokens.
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
// Pastille d'icône + titre. Restylé en tokens (primary par défaut) ; chaque
// section garde son icône.
export function SectionTitle({ icon, label }) {
  return (
    <div className="mb-4 flex items-center gap-2.5">
      <span className="flex size-7 items-center justify-center rounded-lg bg-primary/12 text-primary">
        <Ic size={15} color="currentColor" sw={1.8}>{icon}</Ic>
      </span>
      <span className="text-sm font-semibold tracking-tight text-foreground">{label}</span>
    </div>
  )
}

// ── Field (label au-dessus + contrôle) ─────────────────────────────────────────
export function Field({ label, required, htmlFor, children }) {
  return (
    <div className="flex flex-col gap-1.5">
      {label && <Label htmlFor={htmlFor} required={required}>{label}</Label>}
      {children}
    </div>
  )
}

// ── Image upload zone ─────────────────────────────────────────────────────────
// Aperçu de l'image courante + dropzone. Mêmes validations (type/taille), même
// callback onUpload/onDelete — restylé en tokens.
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
    <div className="flex flex-col gap-2.5">
      <p className="text-xs font-medium text-foreground">{label}</p>

      {/* ── Aperçu de l'image courante ── */}
      {fullUrl && (
        <div className="relative">
          <div className="flex min-h-[110px] items-center justify-center overflow-hidden rounded-lg border border-border bg-muted/40 p-2.5">
            {imgErr ? (
              <div className="flex flex-col items-center gap-1.5 text-muted-foreground">
                <ImageOff className="size-7" aria-hidden="true" />
                <span className="text-[11px]">Aperçu indisponible</span>
              </div>
            ) : (
              <img
                src={fullUrl}
                alt={label}
                onError={() => setImgErr(true)}
                className="max-h-[90px] max-w-full rounded-md object-contain drop-shadow-sm"
              />
            )}
          </div>
          {/* Bouton supprimer */}
          <button
            type="button" onClick={() => { setImgErr(false); onDelete() }} disabled={uploading}
            title="Supprimer"
            className="absolute -right-2 -top-2 flex size-6 items-center justify-center rounded-full border-2 border-card bg-destructive text-destructive-foreground shadow-ui-sm disabled:opacity-60"
          >
            <X className="size-3" aria-hidden="true" />
          </button>
        </div>
      )}

      {/* ── Dropzone ── */}
      <div
        onClick={() => !uploading && inputRef.current?.click()}
        onDragOver={e => { e.preventDefault(); setDrag(true) }}
        onDragLeave={() => setDrag(false)}
        onDrop={handleDrop}
        className={[
          'rounded-lg border-2 border-dashed px-3.5 py-3.5 text-center transition-colors',
          uploading ? 'cursor-default' : 'cursor-pointer',
          drag ? 'border-primary bg-primary/5' : 'border-border bg-muted/40 hover:border-primary/50 hover:bg-accent',
        ].join(' ')}
      >
        {uploading ? (
          <div className="flex items-center justify-center gap-2 text-sm text-muted-foreground">
            <Spinner className="size-4 text-primary" /> Téléversement…
          </div>
        ) : (
          <div className="flex flex-col items-center gap-1">
            <UploadCloud className={drag ? 'size-5 text-primary' : 'size-5 text-muted-foreground'} aria-hidden="true" />
            <p className={['text-xs font-medium', drag ? 'text-primary' : 'text-muted-foreground'].join(' ')}>
              {fullUrl ? 'Remplacer —' : 'Glissez ou'}{' '}
              <span className="text-primary underline">parcourez</span>
            </p>
            <span className="text-[10.5px] text-muted-foreground">{hint}</span>
          </div>
        )}
      </div>

      <input ref={inputRef} type="file" accept={ACCEPTED.join(',')} className="sr-only"
        onChange={e => handleFile(e.target.files[0])}/>
      {err && <p className="text-[11.5px] text-destructive">{err}</p>}
    </div>
  )
}

// ── Référentiel block (Catégories / Fournisseurs) ─────────────────────────────
// Liste éditable inline. Mêmes callbacks onCreate/onUpdate/onDelete, même
// confirmation de suppression (window.confirm) — comportement identique.
export function ReferentielBlock({ title, icon, items, onCreate, onUpdate, onDelete }) {
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
    <Card>
      <CardContent className="pt-4 sm:pt-5">
        <SectionTitle label={title} icon={icon}/>

        <div className="mb-2.5 flex flex-col gap-1.5">
          {items.length === 0 && (
            <EmptyState
              title="Aucun élément"
              description="Ajoutez le premier élément avec le bouton ci-dessous."
              className="py-6"
            />
          )}
          {items.map(item => (
            <div key={item.id} className="flex items-center gap-1.5">
              {editId === item.id ? (
                <>
                  <Input
                    ref={editRef}
                    className="h-8 flex-1 text-sm"
                    value={editName}
                    onChange={e => setEditName(e.target.value)}
                    onKeyDown={e => { if (e.key === 'Enter') doUpdate(); if (e.key === 'Escape') setEditId(null) }}
                  />
                  <Button type="button" size="sm" disabled={busy || !editName.trim()} onClick={doUpdate}>
                    {busy ? '…' : 'OK'}
                  </Button>
                  <Button type="button" size="sm" variant="outline" onClick={() => setEditId(null)}>
                    <X className="size-3.5" aria-hidden="true" />
                  </Button>
                </>
              ) : (
                <>
                  <span className="flex-1 py-1.5 text-sm text-foreground">{item.nom}</span>
                  <IconButton size="sm" variant="ghost" label="Renommer"
                    onClick={() => { setEditId(item.id); setEditName(item.nom) }}>
                    <Pencil className="size-3.5" aria-hidden="true" />
                  </IconButton>
                  <IconButton size="sm" variant="ghost" label="Supprimer"
                    className="text-destructive hover:text-destructive"
                    onClick={() => doDelete(item.id)}>
                    <Trash2 className="size-3.5" aria-hidden="true" />
                  </IconButton>
                </>
              )}
            </div>
          ))}
        </div>

        {creating ? (
          <div className="flex gap-1.5">
            <Input
              ref={inputRef}
              className="h-9 flex-1 text-sm"
              value={newName}
              onChange={e => setNewName(e.target.value)}
              onKeyDown={e => { if (e.key === 'Enter') doCreate(); if (e.key === 'Escape') { setCreating(false); setNewName('') } }}
              placeholder="Nouveau nom…"
            />
            <Button type="button" size="sm" disabled={busy || !newName.trim()} onClick={doCreate}>
              {busy ? '…' : 'Ajouter'}
            </Button>
            <Button type="button" size="sm" variant="outline"
              onClick={() => { setCreating(false); setNewName('') }}>
              <X className="size-3.5" aria-hidden="true" />
            </Button>
          </div>
        ) : (
          <Button type="button" size="sm" variant="outline" onClick={() => setCreating(true)}>
            <Plus className="size-3.5" aria-hidden="true" /> Ajouter
          </Button>
        )}
      </CardContent>
    </Card>
  )
}
