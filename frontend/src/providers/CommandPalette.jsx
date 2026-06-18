// L56 — Palette de commandes globale (⌘K / Ctrl+K). Recherche transverse
// (leads / clients / devis / factures / chantiers / équipements / tickets /
// produits) via l'endpoint serveur existant `/reporting/search` (réutilisé, on
// ne duplique aucune logique back). Résultats groupés, navigables au clavier
// (↑/↓ pour bouger, Entrée pour ouvrir, Échap pour fermer). Saisie débouncée.
//
// S'ouvre sur DEUX déclencheurs (joint avec la lane Header) :
//   (a) l'événement window `taqinor:command-palette` (clic du bouton ⌘K du Header)
//   (b) un raccourci global ⌘K / Ctrl+K.
import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import {
  Dialog, DialogContent, DialogTitle, DialogDescription,
} from '../ui/Dialog'
import reportingApi from '../api/reportingApi'

// Route d'ouverture par type d'entité (aligné sur router/index.jsx). `produit`
// est inclus pour le jour où le back le renvoie ; il pointe vers le stock.
const ROUTE = {
  lead: (id) => `/crm/leads?lead=${id}`,
  client: () => '/crm',
  devis: () => '/ventes/devis',
  facture: () => '/ventes/factures',
  chantier: () => '/chantiers',
  equipement: () => '/equipements',
  ticket: () => '/sav',
  produit: () => '/stock',
}

// Aplati les groupes en une liste indexable pour la navigation clavier.
function flatten(groups) {
  const flat = []
  for (const g of groups) {
    for (const r of g.results || []) flat.push({ ...r, _type: g.type })
  }
  return flat
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const navigate = useNavigate()

  const flat = useMemo(() => flatten(groups), [groups])

  const close = useCallback(() => {
    setOpen(false)
    setQ('')
    setGroups([])
    setError(false)
    setActive(0)
  }, [])

  // ── Déclencheurs d'ouverture : event window + raccourci clavier global ──────
  useEffect(() => {
    const onEvent = () => setOpen(true)
    const onKey = (e) => {
      // ⌘K (mac) / Ctrl+K — ouvre/bascule la palette. Ne pas voler la frappe
      // normale : on n'intercepte QUE la combinaison avec le modificateur.
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        setOpen((v) => !v)
      }
    }
    window.addEventListener('taqinor:command-palette', onEvent)
    window.addEventListener('keydown', onKey)
    return () => {
      window.removeEventListener('taqinor:command-palette', onEvent)
      window.removeEventListener('keydown', onKey)
    }
  }, [])

  // Focus l'input à l'ouverture.
  useEffect(() => {
    if (open) {
      const t = setTimeout(() => inputRef.current?.focus(), 30)
      return () => clearTimeout(t)
    }
    return undefined
  }, [open])

  // ── Recherche débouncée (~250 ms) ───────────────────────────────────────────
  // Tous les setState vivent DANS le callback différé (asynchrone) — aucun
  // setState synchrone dans le corps de l'effet (motif GlobalSearch).
  useEffect(() => {
    if (!open) return undefined
    const term = q.trim()
    const t = setTimeout(() => {
      if (term.length < 2) {
        setGroups([]); setLoading(false); setError(false); setActive(0)
        return
      }
      setLoading(true)
      reportingApi.search(term)
        .then((r) => { setGroups(r.data?.groups ?? []); setError(false) })
        .catch(() => { setGroups([]); setError(true) })
        .finally(() => { setLoading(false); setActive(0) })
    }, term.length < 2 ? 0 : 250)
    return () => clearTimeout(t)
  }, [q, open])

  const go = useCallback((item) => {
    const make = ROUTE[item?._type]
    if (make) navigate(make(item.id))
    close()
  }, [navigate, close])

  // ── Navigation clavier dans la liste ────────────────────────────────────────
  const onKeyDown = useCallback((e) => {
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setActive((i) => (flat.length ? (i + 1) % flat.length : 0))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActive((i) => (flat.length ? (i - 1 + flat.length) % flat.length : 0))
    } else if (e.key === 'Enter') {
      e.preventDefault()
      if (flat[active]) go(flat[active])
    }
    // Échap est géré par le Dialog (onOpenChange) → close().
  }, [flat, active, go])

  // Garde l'élément actif visible.
  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.querySelector('[data-active="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const term = q.trim()
  let idx = -1

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : close())}>
      <DialogContent
        className="cmdk-content"
        showClose={false}
        onKeyDown={onKeyDown}
        aria-label="Palette de commandes"
      >
        {/* Titre/description requis par Radix pour l'accessibilité, masqués
            visuellement (la palette se présente comme une barre de recherche). */}
        <DialogTitle className="sr-only">Recherche rapide</DialogTitle>
        <DialogDescription className="sr-only">
          Recherchez leads, clients, devis, factures, chantiers, équipements et tickets.
        </DialogDescription>

        <div className="cmdk-input-row">
          <Search className="size-4 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            className="cmdk-input"
            placeholder="Rechercher leads, clients, devis, factures, chantiers…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Recherche rapide"
            autoComplete="off"
          />
        </div>

        <div className="cmdk-list" ref={listRef}>
          {term.length < 2 && (
            <div className="cmdk-state">Tapez au moins 2 caractères pour rechercher.</div>
          )}
          {term.length >= 2 && loading && (
            <div className="cmdk-state">Recherche…</div>
          )}
          {term.length >= 2 && !loading && error && (
            <div className="cmdk-state">La recherche a échoué. Réessayez.</div>
          )}
          {term.length >= 2 && !loading && !error && flat.length === 0 && (
            <div className="cmdk-state">Aucun résultat pour « {term} ».</div>
          )}
          {!loading && !error && flat.length > 0 && groups.map((g) => (
            <div key={g.type} className="cmdk-group">
              <div className="cmdk-group-title">{g.label}</div>
              {(g.results || []).map((r) => {
                idx += 1
                const i = idx
                return (
                  <button
                    key={`${g.type}-${r.id}`}
                    type="button"
                    className="cmdk-item"
                    data-active={i === active ? 'true' : 'false'}
                    onMouseMove={() => setActive(i)}
                    onClick={() => go({ ...r, _type: g.type })}
                  >
                    <span className="cmdk-item-label">{r.label}</span>
                    {r.sublabel && <span className="cmdk-item-sub">{r.sublabel}</span>}
                  </button>
                )
              })}
            </div>
          ))}
        </div>

        <div className="cmdk-footer">
          <span><span className="cmdk-kbd">↑</span> <span className="cmdk-kbd">↓</span> naviguer</span>
          <span><span className="cmdk-kbd">↵</span> ouvrir</span>
          <span><span className="cmdk-kbd">Échap</span> fermer</span>
        </div>
      </DialogContent>
    </Dialog>
  )
}

export default CommandPalette
