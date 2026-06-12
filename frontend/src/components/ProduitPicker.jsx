import { useEffect, useMemo, useRef, useState } from 'react'
import {
  groupCatalogue, searchCatalogue, keySpec, prixTtc, sansPrix,
} from '../features/stock/catalogue'

// Picker produit groupé CATÉGORIE → MARQUE → ARTICLE, search-first.
// Conçu pour la saisie ligne à ligne : ouvrir → taper → Entrée (le premier
// résultat est présélectionné) ; ↑/↓ naviguent, Échap ferme. Aucune
// dépendance externe ; composant hoisté (identité stable, pas de perte de
// focus). Les produits sans prix sont visibles mais non sélectionnables.
export default function ProduitPicker({ produits, value, onChange, invalid }) {
  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [cursor, setCursor] = useState(0)
  const rootRef = useRef(null)
  const inputRef = useRef(null)
  const listRef = useRef(null)

  const selected = useMemo(
    () => produits.find(p => String(p.id) === String(value)) ?? null,
    [produits, value])

  // Lignes à plat (en-têtes + articles) dans l'ordre délibéré de la taxonomie
  const { rows, selectables } = useMemo(() => {
    const actifs = produits.filter(p => !p.is_archived)
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

  // Fermeture au clic extérieur
  useEffect(() => {
    if (!open) return
    const onDown = (e) => {
      if (rootRef.current && !rootRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDown)
    return () => document.removeEventListener('mousedown', onDown)
  }, [open])

  useEffect(() => {
    if (open) requestAnimationFrame(() => inputRef.current?.focus())
  }, [open])

  const toggle = () => {
    setOpen(o => {
      if (!o) { setQuery(''); setCursor(0) }
      return !o
    })
  }

  // L'élément sous le curseur reste visible pendant la navigation clavier
  useEffect(() => {
    listRef.current
      ?.querySelector('.pp-item.cursor')
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
      setCursor(c => Math.min(c + 1, selectables.length - 1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setCursor(c => Math.max(c - 1, 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (selectables[cursor]) pick(selectables[cursor])
    }
  }

  return (
    <div className="pp-root" ref={rootRef}>
      <button type="button"
              className={`form-select form-select-sm pp-trigger${invalid ? ' is-invalid' : ''}`}
              onClick={toggle}>
        {selected ? selected.nom : <span className="pp-placeholder">— Produit —</span>}
      </button>
      {open && (
        <div className="pp-pop">
          <input ref={inputRef}
                 className="form-control form-control-sm pp-search"
                 placeholder="Chercher un produit… (Entrée = premier résultat)"
                 value={query}
                 onChange={e => { setQuery(e.target.value); setCursor(0) }}
                 onKeyDown={onKeyDown} />
          <div className="pp-list" ref={listRef}>
            {value && (
              <button type="button" className="pp-item pp-clear" onClick={() => pick(null)}>
                ✕ Aucun produit (ligne libre)
              </button>
            )}
            {rows.map(r => {
              if (r.kind === 'cat') {
                return <div key={r.key} className="pp-cat">{r.label}</div>
              }
              if (r.kind === 'brand') {
                return <div key={r.key} className="pp-brand">{r.label}</div>
              }
              const { p, dispo } = r
              const spec = keySpec(p)
              return (
                <button type="button" key={r.key}
                        disabled={!dispo}
                        className={`pp-item${r.index === cursor ? ' cursor' : ''}${dispo ? '' : ' pp-off'}`}
                        onMouseEnter={() => dispo && setCursor(r.index)}
                        onClick={() => dispo && pick(p)}>
                  <span className="pp-item-nom">{p.nom}</span>
                  {spec && <span className="pp-item-spec">{spec}</span>}
                  <span className="pp-item-prix">
                    {dispo ? `${prixTtc(p).toLocaleString('fr-MA')} DH` : 'prix à renseigner'}
                  </span>
                </button>
              )
            })}
            {rows.length === 0 && (
              <div className="pp-empty">Aucun produit pour « {query} »</div>
            )}
          </div>
        </div>
      )}
    </div>
  )
}
