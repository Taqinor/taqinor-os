import { forwardRef, useEffect, useId, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { AlertCircle, Check, ChevronsUpDown, X } from 'lucide-react'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'
import { pressItem } from './interaction'

/* G23 — Combobox/autocomplete (sélection simple, recherche). Données soit
   statiques (`options`), soit asynchrones via `onSearch(query) => Promise<opts>`.
   États couverts : défaut/hover/focus/désactivé/chargement/erreur/vide.
   Option = { value, label, disabled?, description? }. Clavier + ARIA combobox. */

const triggerBase =
  'flex w-full items-center justify-between gap-2 rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'h-[var(--control-h)] px-[var(--control-px)] text-base sm:text-sm transition-colors ' +
  'focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30'

const norm = (s) => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const Combobox = forwardRef(function Combobox(
  {
    options = [],
    value = null,
    onChange,
    onSearch, // async (query) => option[]
    placeholder = 'Sélectionner…',
    searchPlaceholder = 'Rechercher…',
    emptyText = 'Aucun résultat',
    errorText = 'Erreur de chargement',
    disabled,
    invalid,
    clearable = true,
    className,
    id,
    ...props
  },
  ref,
) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const [asyncOpts, setAsyncOpts] = useState(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(null)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const reqIdRef = useRef(0)
  // VX128 — id stable par option, base pour `aria-activedescendant`.
  const listId = useId()

  // Recherche asynchrone (débounce léger, garde anti-réponse-périmée).
  useEffect(() => {
    if (!open || !onSearch) return undefined
    const reqId = ++reqIdRef.current
    setLoading(true)
    setError(null)
    const t = setTimeout(async () => {
      try {
        const res = await onSearch(query)
        if (reqIdRef.current === reqId) { setAsyncOpts(res || []); setCursor(0) }
      } catch (e) {
        if (reqIdRef.current === reqId) { setError(e); setAsyncOpts([]) }
      } finally {
        if (reqIdRef.current === reqId) setLoading(false)
      }
    }, 200)
    return () => clearTimeout(t)
  }, [open, query, onSearch])

  // Liste filtrée : statique (filtrée localement) ou asynchrone.
  const filtered = useMemo(() => {
    if (onSearch) return asyncOpts || []
    const q = norm(query)
    if (!q) return options
    return options.filter((o) => norm(o.label).includes(q) || norm(o.value).includes(q))
  }, [onSearch, asyncOpts, options, query])

  const selected = useMemo(
    () => (options.concat(asyncOpts || [])).find((o) => String(o.value) === String(value)) || null,
    [options, asyncOpts, value],
  )

  // VX128 — id de l'option active suivant le curseur clavier, posé sur
  // `aria-activedescendant` du champ de recherche : NVDA/VoiceOver annoncent
  // enfin l'option survolée en parcourant la liste (0 occurrence avant).
  const activeOptId = filtered[cursor] ? `${listId}-opt-${cursor}` : undefined

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
    else { setQuery(''); setCursor(0) }
  }, [open])

  useEffect(() => {
    listRef.current?.querySelector('[data-cursor="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [cursor, filtered])

  const pick = (opt) => {
    if (!opt || opt.disabled) return
    onChange?.(opt.value, opt)
    setOpen(false)
  }

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => Math.min(c + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      pick(filtered[cursor])
    } else if (e.key === 'Escape') {
      setOpen(false)
    } else if (e.key === 'Tab' && !e.shiftKey) {
      // VX238(b) — Tab sélectionne l'option courante SANS bloquer la
      // tabulation (pas de preventDefault) : le focus continue naturellement
      // vers le champ suivant au lieu de blur à vide en perdant la recherche.
      const opt = filtered[cursor]
      if (opt && !opt.disabled) pick(opt)
    }
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <div className={cn('relative', className)}>
        <PopoverPrimitive.Trigger asChild>
          <button
            type="button"
            ref={ref}
            id={id}
            role="combobox"
            aria-expanded={open}
            disabled={disabled}
            aria-invalid={invalid || undefined}
            className={cn(triggerBase, !selected && 'text-muted-foreground')}
            {...props}
          >
            <span className="line-clamp-1 flex-1 text-left">{selected ? selected.label : placeholder}</span>
            <ChevronsUpDown className="size-4 shrink-0 opacity-60" />
          </button>
        </PopoverPrimitive.Trigger>
        {clearable && selected && !disabled && (
          <button
            type="button"
            aria-label="Effacer la sélection"
            onClick={() => onChange?.(null, null)}
            className="absolute inset-y-0 right-8 my-auto grid size-5 place-items-center rounded text-muted-foreground hover:text-foreground"
          >
            <X className="size-3.5" />
          </button>
        )}
      </div>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={6}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="z-[var(--z-popover)] w-[var(--radix-popover-trigger-width)] min-w-48 overflow-hidden rounded-lg border border-border bg-popover p-0 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <div className="border-b border-border p-1.5">
            <input
              ref={inputRef}
              type="text"
              role="searchbox"
              aria-autocomplete="list"
              aria-controls={listId}
              aria-activedescendant={activeOptId}
              autoComplete="off"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0) }}
              onKeyDown={onKeyDown}
              placeholder={searchPlaceholder}
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
            />
          </div>
          <div ref={listRef} id={listId} role="listbox" className="max-h-60 overflow-y-auto p-1">
            {loading && (
              <div className="flex items-center justify-center gap-2 py-6 text-sm text-muted-foreground">
                <Spinner className="size-4" /> Chargement…
              </div>
            )}
            {!loading && error && (
              <div role="alert" className="flex items-center justify-center gap-2 px-2 py-6 text-center text-sm text-destructive">
                <AlertCircle className="size-4 shrink-0" aria-hidden="true" />
                <span>{(error && error.message) || errorText}</span>
              </div>
            )}
            {!loading && !error && filtered.length === 0 && (
              <div className="py-6 text-center text-sm text-muted-foreground">{emptyText}</div>
            )}
            {!loading && !error && filtered.map((opt, i) => {
              const isSel = String(opt.value) === String(value)
              const isCur = i === cursor
              return (
                <button
                  key={String(opt.value)}
                  id={`${listId}-opt-${i}`}
                  type="button"
                  role="option"
                  aria-selected={isSel}
                  disabled={opt.disabled}
                  data-cursor={isCur || undefined}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => pick(opt)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none',
                    isCur && 'bg-accent text-accent-foreground',
                    opt.disabled && 'cursor-not-allowed opacity-50',
                    pressItem,
                  )}
                >
                  <Check className={cn('size-4 shrink-0', isSel ? 'opacity-100' : 'opacity-0')} />
                  <span className="flex-1 truncate">
                    {opt.label}
                    {opt.description && (
                      <span className="block truncate text-xs text-muted-foreground">{opt.description}</span>
                    )}
                  </span>
                </button>
              )
            })}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
})

export default Combobox
