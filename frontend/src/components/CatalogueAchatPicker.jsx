import { useEffect, useMemo, useRef, useState } from 'react'
import * as PopoverPrimitive from '@radix-ui/react-popover'
import { cn } from '../lib/cn'
import { useActiveDescendant } from '../hooks/useActiveDescendant'
import { formatMAD } from '../lib/format'

/* NTP2P3 — Picker du CATALOGUE INTERNE D'ACHAT (écran demande d'achat).

   Différence essentielle avec `ProduitPicker` (G23), qui reste le picker des
   documents de VENTE : ici la source est `/stock/catalogue-achat/`, qui
   n'expose JAMAIS `prix_vente`. Un demandeur non-admin compose donc sa
   réquisition sans qu'aucune marge ne soit calculable côté client — c'est le
   critère d'acceptation NTP2P3.

   Recherche SERVEUR (`?q=`, nom / SKU / catégorie), débouncée : le catalogue
   d'une société peut être large et la liste complète n'est jamais chargée.

   Props : { items, value, onChange, onSearch, invalid, favoris }
     - `items`    : la page courante du catalogue (fournie par l'appelant) ;
     - `onSearch` : (q) => void, remonte la requête à l'appelant qui interroge
       l'API (le composant reste sans dépendance réseau, donc testable) ;
     - `favoris`  : NTP2P22 — liste d'ids produits épinglés en tête de liste. */
export default function CatalogueAchatPicker({
  items = [], value, onChange, onSearch, invalid, favoris = [],
}) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const { listId, getOptionId, activeId } = useActiveDescendant(cursor)

  const selected = useMemo(
    () => items.find((p) => String(p.id) === String(value)) ?? null,
    [items, value])

  // NTP2P22 — les favoris de l'employé remontent en tête (« déjà commandé »),
  // le reste garde l'ordre alphabétique renvoyé par le serveur.
  const rows = useMemo(() => {
    const rank = new Map(favoris.map((id, i) => [String(id), i]))
    return [...items].sort((a, b) => {
      const ra = rank.has(String(a.id)) ? rank.get(String(a.id)) : Infinity
      const rb = rank.has(String(b.id)) ? rank.get(String(b.id)) : Infinity
      if (ra !== rb) return ra - rb
      return String(a.nom || '').localeCompare(String(b.nom || ''), 'fr')
    })
  }, [items, favoris])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  // Recherche serveur débouncée — jamais déclenchée popover fermé.
  useEffect(() => {
    if (!open || !onSearch) return undefined
    const t = setTimeout(() => onSearch(query), 250)
    return () => clearTimeout(t)
  }, [query, open, onSearch])

  useEffect(() => {
    listRef.current
      ?.querySelector('[data-cursor="true"]')
      ?.scrollIntoView({ block: 'nearest' })
  }, [cursor, open])

  const handleOpenChange = (next) => {
    setOpen(next)
    if (!next) { setQuery(''); setCursor(0) }
  }

  const pick = (p) => {
    onChange(p ? String(p.id) : '', p ?? null)
    setOpen(false)
  }

  const onKeyDown = (e) => {
    if (e.key === 'Escape') { setOpen(false); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setCursor((c) => Math.min(c + 1, rows.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor((c) => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (rows[cursor]) pick(rows[cursor])
    }
  }

  return (
    <PopoverPrimitive.Root open={open} onOpenChange={handleOpenChange}>
      <PopoverPrimitive.Trigger asChild>
        <button
          type="button"
          data-testid="catalogue-achat-trigger"
          aria-invalid={invalid || undefined}
          className={cn(
            'flex h-[var(--control-h-sm)] w-full items-center justify-between gap-2 rounded-md border border-input bg-card px-2.5 text-sm text-foreground shadow-ui-xs transition-colors',
            'focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:border-ring',
            'aria-[invalid=true]:border-destructive aria-[invalid=true]:ring-destructive/30',
          )}
        >
          {selected
            ? <span className="truncate">{selected.nom}</span>
            : <span className="text-muted-foreground">— Catalogue —</span>}
        </button>
      </PopoverPrimitive.Trigger>
      <PopoverPrimitive.Portal>
        <PopoverPrimitive.Content
          align="start"
          sideOffset={4}
          onOpenAutoFocus={(e) => e.preventDefault()}
          className="z-[var(--z-popover)] w-[max(var(--radix-popover-trigger-width),20rem)] overflow-hidden rounded-lg border border-border bg-popover p-0 text-popover-foreground shadow-ui-lg focus:outline-none"
        >
          <div className="border-b border-border p-1.5">
            <input
              ref={inputRef}
              role="combobox"
              aria-expanded={open}
              aria-autocomplete="list"
              aria-controls={listId}
              aria-activedescendant={activeId}
              aria-label="Chercher au catalogue d'achat"
              className="h-8 w-full rounded-md bg-transparent px-2 text-base outline-none placeholder:text-muted-foreground sm:text-sm"
              placeholder="Nom, SKU ou catégorie…"
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
                ✕ Aucun article (ligne libre)
              </button>
            )}
            {rows.map((p, index) => {
              const isCur = index === cursor
              const estFavori = favoris.some((id) => String(id) === String(p.id))
              return (
                <button
                  type="button"
                  key={p.id}
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
                  <span className="flex-1 truncate">
                    {estFavori && <span aria-hidden="true" className="mr-1">★</span>}
                    {p.nom}
                    {p.sku && (
                      <span className="ml-1.5 text-xs text-muted-foreground">{p.sku}</span>
                    )}
                  </span>
                  {p.fournisseur_prefere_nom && (
                    <span className="hidden shrink-0 text-xs text-muted-foreground sm:inline">
                      {p.fournisseur_prefere_nom}
                    </span>
                  )}
                  <span className="shrink-0 text-xs font-medium tabular-nums text-foreground">
                    {`${formatMAD(p.prix_achat_dernier ?? 0, { withSymbol: false })} DH`}
                  </span>
                </button>
              )
            })}
            {rows.length === 0 && (
              <div className="px-2 py-6 text-center text-sm text-muted-foreground">
                Aucun article au catalogue pour cette recherche.
              </div>
            )}
          </div>
          <p className="border-t border-border px-2 py-1.5 text-xs text-muted-foreground">
            Prix d&apos;achat indicatif — donnée interne.
          </p>
        </PopoverPrimitive.Content>
      </PopoverPrimitive.Portal>
    </PopoverPrimitive.Root>
  )
}
