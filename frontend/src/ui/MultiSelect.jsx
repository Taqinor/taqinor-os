import { forwardRef, useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { AlertCircle, Check, ChevronsUpDown, X } from 'lucide-react'
import { cn } from '../lib/cn'
import { Spinner } from './Spinner'
import { pressItem } from './interaction'

/* G23 — MultiSelect (sélection multiple, recherche async ou locale). `value`
   est un tableau de valeurs. Les choix retenus s'affichent en jetons effaçables.
   États : défaut/hover/focus/désactivé/chargement/erreur/vide. Clavier + ARIA. */

const triggerBase =
  'flex w-full items-center justify-between gap-2 rounded-md border border-input bg-card text-foreground shadow-ui-xs ' +
  'min-h-[var(--control-h)] px-[calc(var(--control-px)-2px)] py-1 text-base sm:text-sm transition-colors ' +
  'focus-ring focus-visible:border-ring ' +
  'disabled:cursor-not-allowed disabled:opacity-60 ' +
  'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30'

const norm = (s) => String(s ?? '').toLowerCase().normalize('NFD').replace(/[̀-ͯ]/g, '')

export const MultiSelect = forwardRef(function MultiSelect(
  {
    options = [],
    value = [],
    onChange,
    onSearch, // async (query) => option[]
    placeholder = 'Sélectionner…',
    searchPlaceholder = 'Rechercher…',
    emptyText = 'Aucun résultat',
    errorText = 'Erreur de chargement',
    disabled,
    invalid,
    maxTokens = 99,
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

  const valueSet = useMemo(() => new Set(value.map(String)), [value])

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

  const filtered = useMemo(() => {
    if (onSearch) return asyncOpts || []
    const q = norm(query)
    if (!q) return options
    return options.filter((o) => norm(o.label).includes(q) || norm(o.value).includes(q))
  }, [onSearch, asyncOpts, options, query])

  // Pool de toutes les options connues, pour retrouver le libellé d'un jeton.
  const known = useMemo(() => {
    const m = new Map()
    for (const o of options) m.set(String(o.value), o)
    for (const o of asyncOpts || []) m.set(String(o.value), o)
    return m
  }, [options, asyncOpts])

  const selectedOpts = useMemo(
    () => value.map((v) => known.get(String(v)) || { value: v, label: String(v) }),
    [value, known],
  )

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
    else { setQuery(''); setCursor(0) }
  }, [open])

  useEffect(() => {
    listRef.current?.querySelector('[data-cursor="true"]')?.scrollIntoView({ block: 'nearest' })
  }, [cursor, filtered])

  const toggle = (opt) => {
    if (!opt || opt.disabled) return
    const v = String(opt.value)
    if (valueSet.has(v)) onChange?.(value.filter((x) => String(x) !== v))
    else onChange?.([...value, opt.value])
  }

  const removeToken = (v) => onChange?.(value.filter((x) => String(x) !== String(v)))

  const onKeyDown = (e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => Math.min(c + 1, filtered.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      toggle(filtered[cursor])
    } else if (e.key === 'Backspace' && !query && value.length) {
      removeToken(value[value.length - 1])
    } else if (e.key === 'Escape') {
      setOpen(false)
    }
  }

  const shown = selectedOpts.slice(0, maxTokens)
  const overflow = selectedOpts.length - shown.length

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={setOpen}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          ref={ref}
          id={id}
          role="combobox"
          aria-expanded={open}
          disabled={disabled}
          aria-invalid={invalid || undefined}
          className={cn(triggerBase, className)}
          {...props}
        >
          <span className="flex flex-1 flex-wrap items-center gap-1">
            {selectedOpts.length === 0 && <span className="text-muted-foreground">{placeholder}</span>}
            {shown.map((opt) => (
              <span
                key={String(opt.value)}
                className="inline-flex items-center gap-1 rounded bg-secondary px-1.5 py-0.5 text-xs text-secondary-foreground"
              >
                {opt.label}
                <span
                  role="button"
                  tabIndex={-1}
                  aria-label={`Retirer ${opt.label}`}
                  onClick={(e) => { e.stopPropagation(); removeToken(opt.value) }}
                  className="grid size-3.5 place-items-center rounded-full hover:bg-foreground/10"
                >
                  <X className="size-3" />
                </span>
              </span>
            ))}
            {overflow > 0 && <span className="text-xs text-muted-foreground">+{overflow}</span>}
          </span>
          <ChevronsUpDown className="size-4 shrink-0 opacity-60" />
        </button>
      </PopoverPrimitive.Trigger>
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
              autoComplete="off"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0) }}
              onKeyDown={onKeyDown}
              placeholder={searchPlaceholder}
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
            />
          </div>
          <div ref={listRef} role="listbox" aria-multiselectable className="max-h-60 overflow-y-auto p-1">
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
              const isSel = valueSet.has(String(opt.value))
              const isCur = i === cursor
              return (
                <button
                  key={String(opt.value)}
                  type="button"
                  role="option"
                  aria-selected={isSel}
                  disabled={opt.disabled}
                  data-cursor={isCur || undefined}
                  onMouseEnter={() => setCursor(i)}
                  onClick={() => toggle(opt)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none',
                    isCur && 'bg-accent text-accent-foreground',
                    opt.disabled && 'cursor-not-allowed opacity-50',
                    pressItem,
                  )}
                >
                  <span className={cn(
                    'grid size-4 shrink-0 place-items-center rounded border',
                    isSel ? 'border-primary bg-primary text-primary-foreground' : 'border-input',
                  )}>
                    {isSel && <Check className="size-3" strokeWidth={3} />}
                  </span>
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

export default MultiSelect
