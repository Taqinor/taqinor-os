import { forwardRef, useId, useRef, useState } from 'react'
import { UploadCloud } from 'lucide-react'
import { cn } from '../lib/cn'
import { validateFiles, formatFileSize } from './file-utils'

/* G26 — Dropzone / FileUpload accessible. Glisser-déposer + clic clavier,
   validation type/taille (file-utils.js), états défaut/survol/drag/erreur/
   désactivé. Ne fait PAS l'upload réseau lui-même : il remet les fichiers
   validés via `onFiles(File[])` — l'appelant garde la main sur ses appels API
   (préservation stricte des flux existants). La barre de progression
   s'affiche via la prop `progress` (0–100) pilotée par l'appelant. */

const ACCEPT_LABEL = (accept) =>
  accept
    ? accept
        .split(',')
        .map((s) => s.trim().replace(/^\./, '').replace('image/', '').replace('application/', ''))
        .filter(Boolean)
        .join(' · ')
        .toUpperCase()
    : ''

export const FileUpload = forwardRef(function FileUpload(
  {
    accept = '',
    maxSize, // octets
    multiple = false,
    disabled = false,
    onFiles, // (File[]) => void  — fichiers déjà validés
    onReject, // (rejected: {file,error}[]) => void
    progress, // number 0–100 | undefined
    busy = false,
    hint, // texte d'aide additionnel
    className,
    children,
    id,
    ...props
  },
  ref,
) {
  const autoId = useId()
  const inputId = id || autoId
  const inputRef = useRef(null)
  const [dragging, setDragging] = useState(false)

  const handle = (fileList) => {
    const { accepted, rejected } = validateFiles(fileList, { accept, maxSize, multiple })
    if (rejected.length) onReject?.(rejected)
    if (accepted.length) onFiles?.(accepted)
  }

  const onDrop = (e) => {
    e.preventDefault()
    setDragging(false)
    if (disabled || busy) return
    handle(e.dataTransfer.files)
  }

  const open = () => { if (!disabled && !busy) inputRef.current?.click() }

  const onKeyDown = (e) => {
    if ((e.key === 'Enter' || e.key === ' ') && !disabled && !busy) {
      e.preventDefault()
      open()
    }
  }

  const showProgress = typeof progress === 'number' && progress >= 0 && progress < 100

  return (
    <div className={className}>
      <input
        ref={(node) => {
          inputRef.current = node
          if (typeof ref === 'function') ref(node)
          else if (ref) ref.current = node
        }}
        id={inputId}
        type="file"
        accept={accept || undefined}
        multiple={multiple}
        disabled={disabled}
        className="sr-only"
        onChange={(e) => { handle(e.target.files); e.target.value = '' }}
        {...props}
      />
      <div
        role="button"
        tabIndex={disabled ? -1 : 0}
        aria-disabled={disabled || undefined}
        aria-busy={busy || undefined}
        aria-controls={inputId}
        onClick={open}
        onKeyDown={onKeyDown}
        onDrop={onDrop}
        onDragOver={(e) => { e.preventDefault(); if (!disabled && !busy) setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        className={cn(
          'flex flex-col items-center justify-center gap-3 rounded-xl border-2 border-dashed px-6 py-10 text-center transition-colors',
          'focus-ring',
          dragging
            ? 'border-primary bg-primary/5'
            : 'border-border bg-muted/40 hover:border-primary/50 hover:bg-accent',
          (disabled || busy) && 'cursor-not-allowed opacity-60 hover:border-border hover:bg-muted/40',
          !disabled && !busy && 'cursor-pointer',
        )}
      >
        {children || (
          <>
            <span className="grid size-12 place-items-center rounded-full bg-background text-muted-foreground">
              <UploadCloud className="size-6" aria-hidden="true" />
            </span>
            <div>
              <p className="text-sm font-medium text-foreground">
                Glissez un fichier ici ou <span className="text-primary underline">cliquez pour choisir</span>
              </p>
              <p className="mt-1 text-xs text-muted-foreground">
                {ACCEPT_LABEL(accept)}
                {ACCEPT_LABEL(accept) && maxSize ? ' — ' : ''}
                {maxSize ? `max ${formatFileSize(maxSize)}` : ''}
                {hint ? (ACCEPT_LABEL(accept) || maxSize ? ' · ' : '') + hint : ''}
              </p>
            </div>
          </>
        )}

        {showProgress && (
          <div className="mt-1 w-full max-w-xs" aria-hidden={false}>
            <div
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={progress}
              className="h-1.5 w-full overflow-hidden rounded-full bg-muted"
            >
              <div className="h-full rounded-full bg-primary transition-[width] duration-200" style={{ width: `${progress}%` }} />
            </div>
            <p className="mt-1 text-xs tabular-nums text-muted-foreground">Envoi… {progress}%</p>
          </div>
        )}
      </div>
    </div>
  )
})

export default FileUpload
