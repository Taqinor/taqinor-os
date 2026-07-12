import { forwardRef, useEffect, useId, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { Clock } from 'lucide-react'
import { cn } from '../lib/cn'
import { parseTime, formatTime, timeOptions } from './date-utils'

/* G24 — TimePicker HH:mm (planification de relance). Saisie libre au clavier
   (validée par parseTime) + liste de créneaux navigable. Aucune lib externe. */

const fieldBase =
  'flex w-full items-center gap-2 rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'h-[var(--control-h)] px-[var(--control-px)] text-base sm:text-sm transition-colors ' +
  'focus-ring focus-within:border-ring ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30'

export const TimePicker = forwardRef(function TimePicker(
  { value = '', onChange, step = 30, disabled, invalid, placeholder = 'HH:mm', className, id, ...props },
  ref,
) {
  const [open, setOpen] = useState(false)
  const [text, setText] = useState(value)
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  // VX128 — id stable par option, base pour `aria-activedescendant` (voir
  // Combobox.jsx : ici l'input porte déjà role="combobox" directement).
  const listId = useId()

  useEffect(() => { setText(value) }, [value])

  const options = useMemo(() => timeOptions(step), [step])
  const activeOptId = open && options[cursor] ? `${listId}-opt-${cursor}` : undefined

  // Position initiale du curseur = créneau le plus proche de la valeur courante.
  useEffect(() => {
    if (!open) return
    const i = options.indexOf(value)
    setCursor(i >= 0 ? i : 0)
  }, [open, value, options])

  useEffect(() => {
    if (open) {
      listRef.current
        ?.querySelector('[data-cursor="true"]')
        ?.scrollIntoView({ block: 'nearest' })
    }
  }, [cursor, open])

  const commit = (raw) => {
    const t = parseTime(raw)
    if (t) {
      const formatted = formatTime(t)
      setText(formatted)
      onChange?.(formatted)
    } else if (raw === '') {
      onChange?.('')
    } else {
      setText(value) // entrée invalide → on restaure
    }
  }

  const pick = (opt) => {
    setText(opt)
    onChange?.(opt)
    setOpen(false)
    inputRef.current?.focus()
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      if (!open) { setOpen(true); return }
      setCursor((c) => Math.min(c + 1, options.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      if (!open) { setOpen(true); return }
      setCursor((c) => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (open && options[cursor]) pick(options[cursor])
      else commit(text)
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Anchor asChild>
        <div
          className={cn(fieldBase, disabled && 'cursor-not-allowed opacity-60', className)}
          aria-invalid={invalid || undefined}
        >
          <Clock className="size-4 shrink-0 text-muted-foreground" />
          <input
            ref={(node) => {
              inputRef.current = node
              if (typeof ref === 'function') ref(node)
              else if (ref) ref.current = node
            }}
            id={id}
            type="text"
            inputMode="numeric"
            role="combobox"
            aria-expanded={open}
            aria-autocomplete="list"
            aria-controls={listId}
            aria-activedescendant={activeOptId}
            autoComplete="off"
            disabled={disabled}
            placeholder={placeholder}
            value={text}
            onChange={(e) => { setText(e.target.value); if (!open) setOpen(true) }}
            onFocus={() => setOpen(true)}
            onBlur={() => commit(text)}
            onKeyDown={onKeyDown}
            className="w-full bg-transparent tabular-nums outline-none placeholder:text-muted-foreground disabled:cursor-not-allowed"
            {...props}
          />
        </div>
      </PopoverPrimitive.Anchor>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="z-[var(--z-popover)] max-h-56 w-[var(--radix-popover-trigger-width)] min-w-28 overflow-y-auto rounded-lg border border-border bg-popover p-1 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <div ref={listRef} id={listId} role="listbox">
            {options.map((opt, i) => {
              const isCur = i === cursor
              const isSel = opt === value
              return (
                <button
                  key={opt}
                  id={`${listId}-opt-${i}`}
                  type="button"
                  role="option"
                  aria-selected={isSel}
                  data-cursor={isCur || undefined}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => pick(opt)}
                  className={cn(
                    'flex w-full items-center rounded-md px-2 py-1.5 text-sm tabular-nums outline-none',
                    isCur && 'bg-accent text-accent-foreground',
                    isSel && 'font-semibold text-primary',
                  )}
                >
                  {opt}
                </button>
              )
            })}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
})

export default TimePicker
