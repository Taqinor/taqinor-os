import { useEffect, useRef, useState } from 'react'
import { Check, X } from 'lucide-react'
import { cn } from '../../lib/cn'
import { Input } from '../Input'

/* ============================================================================
   H32 — Édition de cellule en place avec validation + sauvegarde + annulation.
   - Double-clic (ou Entrée sur cellule focus) → mode édition.
   - `validate(value, row) -> string|null` : message d'erreur ou null si valide.
   - `onSave(value, row)` est appelé à la validation ; le parent gère le toast
     succès + le bouton « Annuler » (undo) via sonner.
   - Échap annule, Entrée valide. Erreur affichée sous le champ (aria-invalid).
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
}) {
  const [editing, setEditing] = useState(false)
  const [draft, setDraft] = useState('')
  const [error, setError] = useState(null)
  const inputRef = useRef(null)

  useEffect(() => {
    if (editing && inputRef.current) {
      inputRef.current.focus()
      inputRef.current.select?.()
    }
  }, [editing])

  const display = format ? format(value, row) : value ?? '—'

  function begin() {
    setDraft(value ?? '')
    setError(null)
    setEditing(true)
  }

  function commit() {
    const err = validate ? validate(draft, row) : null
    if (err) {
      setError(err)
      return
    }
    setEditing(false)
    setError(null)
    if (String(draft) !== String(value ?? '')) onSave?.(draft, row)
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
          if (e.key === 'Enter' || e.key === 'F2') {
            e.preventDefault()
            begin()
          }
        }}
        className={cn(
          'block w-full truncate rounded px-1 py-0.5 text-left',
          'hover:bg-accent/60 focus-ring',
          align === 'right' && 'text-right',
          align === 'center' && 'text-center',
          className,
        )}
        title="Double-cliquez pour modifier"
        aria-label={`Modifier — valeur actuelle ${String(display)}`}
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
