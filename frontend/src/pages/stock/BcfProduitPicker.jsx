import { useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../../lib/cn'
import { useActiveDescendant } from '../../hooks/useActiveDescendant'
import { formatMAD } from '../../lib/format'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../../features/stock/catalogue'

/* L723 — Picker produit dédié au contexte ACHAT (bon de commande fournisseur).
   Contrairement au ProduitPicker partagé (devis/installation) qui grise les
   produits sans prix de VENTE, ce picker les rend SÉLECTIONNABLES : un BCF est
   un document interne d'achat (≠ devis), donc une pompe dont le prix de vente
   n'est pas encore renseigné doit rester commandable. Les articles sans prix
   de vente portent simplement la mention « sans prix de vente » au lieu d'être
   grisés. API identique : { produits, value, onChange, invalid }. */
export default function BcfProduitPicker({ produits, value, onChange, invalid }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  // VX191 — `aria-activedescendant` : même contrat que ProduitPicker (VX191).
  const { listId, getOptionId, activeId } = useActiveDescendant(cursor)

  const selected = useMemo(
    () => produits.find((p) => String(p.id) === String(value)) ?? null,
    [produits, value])

  // Lignes à plat (en-têtes + articles) ; TOUS les articles sont sélectionnables.
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
          rows.push({ kind: 'item', p, key: `p-${p.id}`, index: selectables.length })
          selectables.push(p)
        }
      }
    }
    return { rows, selectables }
  }, [produits, query])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  const handleOpenChange = (next) => {
    setOpen(next)
    if (!next) { setQuery(''); setCursor(0) }
  }

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
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-controls={listId}
              aria-activedescendant={activeId}
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
              placeholder="Chercher un produit à commander… (Entrée = premier résultat)"
              value={query}
              onChange={(e) => { setQuery(e.target.value); setCursor(0) }}
              onKeyDown={onKeyDown}
            />
          </div>
          <div className="max-h-72 overflow-y-auto p-1" ref={listRef} role="listbox" id={listId}>
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
              const { p, index } = r
              const spec = keySpec(p)
              const isCur = index === cursor
              const noPrix = sansPrix(p)
              return (
                <button
                  type="button"
                  key={r.key}
                  id={getOptionId(index)}
                  role="option"
                  aria-selected={String(p.id) === String(value)}
                  data-cursor={isCur ? 'true' : undefined}
                  onMouseEnter={() => setCursor(index)}
                  onClick={() => pick(p)}
                  className={cn(
                    'flex w-full items-center gap-2 rounded-md px-2 py-1.5 text-left text-sm outline-none',
                    isCur && 'bg-accent text-accent-foreground',
                  )}
                >
                  <span className="flex-1 truncate">{p.nom}</span>
                  {spec && <span className="shrink-0 text-xs text-muted-foreground">{spec}</span>}
                  <span className={cn('shrink-0 text-xs tabular-nums', noPrix ? 'italic text-muted-foreground' : 'font-medium text-foreground')}>
                    {noPrix ? 'sans prix de vente' : `${formatMAD(prixTtc(p), { withSymbol: false })} DH`}
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
