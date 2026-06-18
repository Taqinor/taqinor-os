import { useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../lib/cn'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../features/stock/catalogue'

/* G23 — Picker produit groupé CATÉGORIE → MARQUE → ARTICLE, search-first.
   Conçu pour la saisie ligne à ligne : ouvrir → taper → Entrée (le premier
   résultat est présélectionné) ; ↑/↓ naviguent, Échap ferme. Les produits sans
   prix sont visibles mais non sélectionnables.

   Reconstruit sur le Popover (G28) + jetons sémantiques (les anciennes classes
   pp-* d'index.css ne sont plus utilisées). Props/API préservés 1:1 :
   { produits, value, onChange, invalid }. */
export default function ProduitPicker({ produits, value, onChange, invalid }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)

  const selected = useMemo(
    () => produits.find((p) => String(p.id) === String(value)) ?? null,
    [produits, value])

  // Lignes à plat (en-têtes + articles) dans l'ordre délibéré de la taxonomie
  const { rows, selectables } = useMemo(() => {
    const actifs = produits.filter((p) => !p.is_archived)
    const matches = searchCatalogue(actifs, query)
    const rows = []
    const selectables = []
    for (const cat of groupCatalogue(matches)) {
      rows.push({ kind: 'cat', label: cat.nom, key: `c-${cat.nom}` })
      for (const b of cat.brands) {
        rows.push({ kind: 'brand', label: b.marque, key: `b-${cat.nom}-${b.marque}` })
        for (const p of b.items) {
          const dispo = !sansPrix(p)
          rows.push({ kind: 'item', p, dispo, key: `p-${p.id}`,
                      index: dispo ? selectables.length : -1 })
          if (dispo) selectables.push(p)
        }
      }
    }
    return { rows, selectables }
  }, [produits, query])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  // Réinitialise la recherche à la fermeture (hors effet → pas de cascade).
  const handleOpenChange = (next) => {
    setOpen(next)
    if (!next) { setQuery(''); setCursor(0) }
  }

  // L'élément sous le curseur reste visible pendant la navigation clavier
  useEffect(() => {
    listRef.current
      ?.querySelector('[data-cursor="true"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [cursor, open])

  const pick = (p) => {
    onChange(p ? String(p.id) : '')
    setOpen(false)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { setOpen(false); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => Math.min(c + 1, selectables.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectables[cursor]) pick(selectables[cursor])
    }
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={handleOpenChange}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          aria-invalid={invalid || undefined}
          className={cn(
            'flex h-[var(--control-h-sm)] w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 text-sm text-foreground shadow-ui-xs transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring',
            'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
          )}
        >
          {selected
            ? <span className="truncate">{selected.nom}</span>
            : <span className="text-muted-foreground">— Produit —</span>}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={4}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="z-[var(--z-popover)] w-[max(var(--radix-popover-trigger-width),18rem)] overflow-hidden rounded-lg border border-border bg-popover p-0 text-popover-foreground shadow-ui-lg data-[state=open]:animate-pop-in data-[state=closed]:animate-pop-out focus:outline-none"
        >
          <div className="border-b border-border p-1.5">
            <input
              ref={inputRef}
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
              placeholder="Chercher un produit… (Entrée = premier résultat)"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0) }}
              onKeyDown={onKeyDown}
            />
          </div>
          <div className="max-h-72 overflow-y-auto p-1" ref={listRef} role="listbox">
            {value && (
              <button
                type="button"
                onClick={() => pick(null)}
                className="flex w-full items-center rounded-md px-2 py-1.5 text-left text-sm text-muted-foreground outline-none hover:bg-accent"
              >
                ✕ Aucun produit (ligne libre)
              </button>
            )}
            {rows.map((r) => {
              if (r.kind === 'cat') {
                return (
                  <div key={r.key} className="px-2 pb-1 pt-2 text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    {r.label}
                  </div>
                )
              }
              if (r.kind === 'brand') {
                return (
                  <div key={r.key} className="px-2 py-0.5 text-xs font-medium text-foreground/70">
                    {r.label}
                  </div>
                )
              }
              const { p, dispo, index } = r
              const spec = keySpec(p)
              const isCur = index === cursor
              return (
                <button
                  type="button"
                  key={r.key}
                  role="option"
                  aria-selected={String(p.id) === String(value)}
                  aria-disabled={!dispo || undefined}
                  disabled={!dispo}
                  data-cursor={dispo && isCur ? 'true' : undefined}
                  onMouseEnter={() => dispo && setCursor(index)}
                  onClick={() => dispo && pick(p)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none',
                    dispo && isCur && 'bg-accent text-accent-foreground',
                    !dispo && 'cursor-not-allowed opacity-50',
                  )}
                >
                  <span className="flex-1 truncate">{p.nom}</span>
                  {spec && <span className="shrink-0 text-xs text-muted-foreground">{spec}</span>}
                  <span className={cn('shrink-0 text-xs tabular-nums', dispo ? 'font-medium text-foreground' : 'italic text-muted-foreground')}>
                    {dispo ? `${prixTtc(p).toLocaleString('fr-MA')} DH` : 'prix à renseigner'}
                  </span>
                </button>
              )
            })}
            {rows.length === 0 && (
              <div className="px-2 py-6 text-center text-sm text-muted-foreground">
                Aucun produit pour «&nbsp;{query}&nbsp;»
              </div>
            )}
          </div>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
