import { useEffect, useRef, useState } from 'react'
import { Check, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Input } from '../Input'
import { Spinner } from '../Spinner'

/* ============================================================================
   H32 — Édition de cellule en place avec validation + sauvegarde + annulation.
   - Double-clic (ou Entrée sur cellule focus) → mode édition.
   - `validate(value, row) -> string|null` : message d'erreur ou null si valide.
   - `onSave(value, row)` est appelé à la validation, ATTENDU (`await`) — s'il
     retourne une promesse qui REJETTE (ex. PATCH serveur refusé), la cellule
     RESTE ouverte avec le message d'erreur au lieu de se refermer en silence.
   - Échap annule, Entrée valide. Erreur affichée sous le champ (aria-invalid).
   - `readOnly` (VX127) : double-clic/Entrée/F2 sans effet, aucun mode édition
     — distinct d'un simple manque de `onSave` (le style reste « lecture
     seule », pas grisé comme un `disabled`).
   Contrôlé côté affichage par `value` ; ce composant ne mute que son brouillon.
   ========================================================================== */
export function EditableCell({
  value,
  row,
  format,
  validate,
  onSave,
  align = 'left',
  inputType = 'text',
  className,
  readOnly = false,
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)
  const [saving, setSaving] = useState(false)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select?.()
    }
  }, [editing])

  const display = format ? format(value, row) : value ?? '—'

  function begin() {
    if (readOnly) return
    setDraft(value ?? '')
    setError(null)
    setEditing(true)
  }

  async function commit() {
    // Garde anti-double-commit : `disabled={saving}` sur l'input peut lui
    // faire perdre le focus (→ un second onBlur/commit) pendant l'attente.
    if (saving) return
    const err = validate ? validate(draft, row) : null
    if (err) {
      setError(err)
      return
    }
    if (String(draft) === String(value ?? '')) {
      setEditing(false)
      setError(null)
      return
    }
    setSaving(true)
    setError(null)
    try {
      await onSave?.(draft, row)
      setEditing(false)
    } catch (e) {
      // Rejet serveur : la cellule RESTE ouverte (rouverte), message affiché
      // au lieu de se refermer en silence sur un échec.
      setError(e?.response?.data?.detail || e?.message || 'Échec de l’enregistrement — réessayez.')
    } finally {
      setSaving(false)
    }
  }

  function cancel() {
    setEditing(false)
    setError(null)
  }

  if (!editing) {
    return (
      <button
        type="button"
        onDoubleClick={begin}
        onKeyDown={(e) => {
          if (readOnly) return
          if (e.key === 'Enter' || e.key === 'F2') {
            e.preventDefault()
            begin()
          }
        }}
        className={cn(
          'block w-full truncate rounded px-1 py-0.5 text-left',
          readOnly ? 'cursor-default' : 'hover:bg-accent/60 focus-ring',
          align === 'right' && 'text-right',
          align === 'center' && 'text-center',
          className,
        )}
        title={readOnly ? undefined : 'Double-cliquez pour modifier'}
        aria-readonly={readOnly || undefined}
        aria-label={readOnly ? undefined : `Modifier — valeur actuelle ${String(display)}`}
      >
        {display}
      </button>
    )
  }

  return (
    <div className="flex flex-col gap-1">
      <div className="flex items-center gap-1">
        <Input
          ref={inputRef}
          type={inputType}
          value={draft}
          invalid={!!error}
          disabled={saving}
          onChange={(e) => {
            setDraft(e.target.value)
            if (error) setError(null)
          }}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              e.preventDefault()
              commit()
            } else if (e.key === 'Escape') {
              e.preventDefault()
              cancel()
            }
          }}
          onBlur={commit}
          className="h-7 px-2 text-sm"
          aria-describedby={error ? 'cell-edit-error' : undefined}
        />
        {saving ? (
          // VX127 — état « enregistrement en cours » discret : jusqu'ici
          // `onSave` était fire-and-forget, aucun retour visuel entre le
          // commit et la fermeture de la cellule.
          <span
            className="flex size-6 shrink-0 items-center justify-center text-muted-foreground"
            role="status"
            aria-live="polite"
          >
            <Spinner className="size-4" aria-hidden="true" />
            <span className="sr-only">Enregistrement…</span>
          </span>
        ) : (
          <>
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={commit}
              aria-label="Valider"
              className="flex size-6 shrink-0 items-center justify-center rounded text-success hover:bg-success/10"
            >
              <Check className="size-4" />
            </button>
            <button
              type="button"
              onMouseDown={(e) => e.preventDefault()}
              onClick={cancel}
              aria-label="Annuler"
              className="flex size-6 shrink-0 items-center justify-center rounded text-muted-foreground hover:bg-muted"
            >
              <X className="size-4" />
            </button>
          </>
        )}
      </div>
      {error && (
        <p id="cell-edit-error" className="text-xs text-destructive">
          {error}
        </p>
      )}
    </div>
  )
}

export default EditableCell
