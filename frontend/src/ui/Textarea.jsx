import { forwardRef, useEffect, useRef, useState } from 'react'
import { cn } from '../lib/cn'
import { SANITIZE_PRESETS } from './Input'

/* G22 — Zone de texte multi-ligne (16px mobile anti-zoom).
   VX124 — caret-primary : curseur de saisie teinté marque (voir Input.jsx).
   VX127 — `readOnly` ≠ `disabled` (voir Input.jsx) : fond distinct, curseur
   par défaut, texte pleine opacité et toujours sélectionnable/copiable.
   VX129 — pack de complétude : `autoResize` (grandit avec le contenu, plus
   de redimensionnement navigateur manuel) + `maxLength` avec compteur
   « n/max » visible — jusqu'ici un Textarea nu (0 des deux).
   VX174 — même prop `sanitize` que Input.jsx (source unique SANITIZE_PRESETS). */
export const Textarea = forwardRef(function Textarea(
  { className, invalid, autoResize, maxLength, onChange, value, defaultValue, sanitize, ...props },
  ref,
) {
  const innerRef = useRef(null)
  const [length, setLength] = useState(() => {
    const initial = value ?? defaultValue
    return typeof initial === 'string' ? initial.length : 0
  })
  const sanitizeProps = sanitize ? SANITIZE_PRESETS[sanitize] : null

  const resize = () => {
    const node = innerRef.current
    if (!autoResize || !node) return
    node.style.height = 'auto'
    node.style.height = `${node.scrollHeight}px`
  }

  useEffect(() => { resize() }, [value, autoResize])

  const textarea = (
    <textarea
      ref={(node) => {
        innerRef.current = node
        if (typeof ref === 'function') ref(node)
        else if (ref) ref.current = node
      }}
      aria-invalid={invalid || undefined}
      value={value}
      defaultValue={defaultValue}
      maxLength={maxLength}
      onChange={(e) => {
        if (maxLength) setLength(e.target.value.length)
        onChange?.(e)
        resize()
      }}
      {...sanitizeProps}
      className={cn(
        'flex min-h-20 w-full rounded-md border border-input bg-card px-3 py-2 text-foreground shadow-ui-xs',
        'transition-colors placeholder:text-muted-foreground caret-primary',
        'focus-ring focus-visible:border-ring',
        'disabled:cursor-not-allowed disabled:opacity-60',
        'read-only:cursor-default read-only:bg-muted/40 read-only:opacity-100',
        'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
        'text-base sm:text-sm',
        autoResize && 'resize-none overflow-hidden',
        className,
      )}
      {...props}
    />
  )

  if (!maxLength) return textarea

  return (
    <div className="flex flex-col gap-1">
      {textarea}
      <span
        className={cn(
          'self-end text-xs tabular-nums text-muted-foreground',
          length >= maxLength && 'text-destructive',
        )}
        aria-live="polite"
      >
        {length}/{maxLength}
      </span>
    </div>
  )
})

export default Textarea
