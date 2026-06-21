// L56 / I134 — Palette de commandes globale (⌘K / Ctrl+K).
//   • Recherche transverse (leads / clients / devis / factures / chantiers /
//     équipements / tickets / produits) via l'endpoint serveur existant
//     `/reporting/search` (réutilisé — on ne duplique aucune logique back).
//   • Mode « Actions » : navigation directe (dérivée des raccourcis « g x »),
//     affiché à vide et filtré à la frappe, avec une puce de raccourci par ligne.
//   • « Récents » : entités récemment ouvertes via la palette, affichées à vide.
//   • Navigation clavier (↑/↓ pour bouger, Entrée pour ouvrir, Échap pour fermer).
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
import { filterActions, readRecentEntities, pushRecentEntity } from './commandActions'

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

// Libellé de groupe par type d'entité — sert d'étiquette discrète aux récents.
const TYPE_LABEL = {
  lead: 'Lead',
  client: 'Client',
  devis: 'Devis',
  facture: 'Facture',
  chantier: 'Chantier',
  equipement: 'Équipement',
  ticket: 'SAV',
  produit: 'Produit',
}

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [groups, setGroups] = useState([])
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState(false)
  const [active, setActive] = useState(0)
  const [recent, setRecent] = useState([])
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const navigate = useNavigate()

  const term = q.trim()
  const actions = useMemo(() => filterActions(term), [term])

  // Sections de rendu + liste APLATIE (indexable clavier) construites en une
  // passe, dans l'ordre d'affichage : Actions → Récents (à vide) → Résultats.
  const { sections, flat } = useMemo(() => {
    const secs = []
    const f = []
    // « Actions » — toujours présentes si au moins une correspond à la requête.
    if (actions.length) {
      const rows = actions.map((a) => {
        const index = f.length
        f.push({ kind: 'action', action: a })
        return { ...a, index }
      })
      secs.push({ key: 'actions', title: 'Actions', kind: 'action', rows })
    }
    if (term.length < 2) {
      // « Récents » (entités) à vide.
      if (recent.length) {
        const rows = recent.map((e, i) => {
          const index = f.length
          f.push({ kind: 'recent', entity: e })
          return { ...e, _i: i, index }
        })
        secs.push({ key: 'recent', title: 'Récents', kind: 'recent', rows })
      }
    } else {
      // Résultats serveur groupés par entité.
      for (const g of groups) {
        const rows = (g.results || []).map((r) => {
          const index = f.length
          f.push({ kind: 'result', type: g.type, item: r })
          return { ...r, index }
        })
        if (rows.length) secs.push({ key: `g-${g.type}`, title: g.label, kind: 'result', type: g.type, rows })
      }
    }
    return { sections: secs, flat: f }
  }, [actions, recent, groups, term])

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

  // À l'ouverture : focus l'input et (re)charge la liste des récents.
  useEffect(() => {
    if (open) {
      setRecent(readRecentEntities())
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
  }, [q, open]) // eslint-disable-line react-hooks/exhaustive-deps

  // Garde l'index actif dans les bornes quand la liste change.
  useEffect(() => {
    setActive((i) => (flat.length ? Math.min(i, flat.length - 1) : 0))
  }, [flat.length])

  // Ouvre une cible quelconque de la liste aplatie.
  const activate = useCallback((entry) => {
    if (!entry) return
    if (entry.kind === 'action') {
      navigate(entry.action.to)
    } else if (entry.kind === 'recent') {
      const make = ROUTE[entry.entity.type]
      if (make) navigate(make(entry.entity.id))
    } else if (entry.kind === 'result') {
      const make = ROUTE[entry.type]
      // Mémorise l'entité ouverte pour la section « Récents ».
      pushRecentEntity({ type: entry.type, id: entry.item.id, label: entry.item.label })
      if (make) navigate(make(entry.item.id))
    }
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
      if (flat[active]) activate(flat[active])
    }
    // Échap est géré par le Dialog (onOpenChange) → close().
  }, [flat, active, activate])

  // Garde l'élément actif visible.
  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.querySelector('[data-active="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [active, open])

  const showSearchStates = term.length >= 2

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
          Recherchez leads, clients, devis, factures, chantiers, équipements et tickets, ou lancez une action.
        </DialogDescription>

        <div className="cmdk-input-row">
          <Search className="size-4 text-muted-foreground" aria-hidden="true" />
          <input
            ref={inputRef}
            type="text"
            className="cmdk-input"
            placeholder="Rechercher ou lancer une action…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
            aria-label="Recherche rapide"
            autoComplete="off"
          />
        </div>

        <div className="cmdk-list" ref={listRef}>
          {/* États de recherche (seulement en mode recherche). */}
          {showSearchStates && loading && (
            <div className="cmdk-state">Recherche…</div>
          )}
          {showSearchStates && !loading && error && (
            <div className="cmdk-state">La recherche a échoué. Réessayez.</div>
          )}
          {showSearchStates && !loading && !error && flat.length === 0 && (
            <div className="cmdk-state">Aucun résultat pour « {term} ».</div>
          )}

          {sections.map((sec) => (
            <div key={sec.key} className="cmdk-group">
              <div className="cmdk-group-title">{sec.title}</div>
              {sec.rows.map((r) => {
                const i = r.index
                if (sec.kind === 'action') {
                  return (
                    <button
                      key={`action-${r.id}`}
                      type="button"
                      className="cmdk-item"
                      data-active={i === active ? 'true' : 'false'}
                      onMouseMove={() => setActive(i)}
                      onClick={() => activate({ kind: 'action', action: r })}
                    >
                      <span className="cmdk-item-label">{r.label}</span>
                      {r.keys && <span className="cmdk-kbd cmdk-item-kbd">{r.keys}</span>}
                    </button>
                  )
                }
                if (sec.kind === 'recent') {
                  return (
                    <button
                      key={`recent-${r.type}-${r.id}`}
                      type="button"
                      className="cmdk-item"
                      data-active={i === active ? 'true' : 'false'}
                      onMouseMove={() => setActive(i)}
                      onClick={() => activate({ kind: 'recent', entity: r })}
                    >
                      <span className="cmdk-item-label">{r.label || TYPE_LABEL[r.type] || r.type}</span>
                      {TYPE_LABEL[r.type] && <span className="cmdk-item-sub">{TYPE_LABEL[r.type]}</span>}
                    </button>
                  )
                }
                // résultat de recherche
                return (
                  <button
                    key={`${sec.type}-${r.id}`}
                    type="button"
                    className="cmdk-item"
                    data-active={i === active ? 'true' : 'false'}
                    onMouseMove={() => setActive(i)}
                    onClick={() => activate({ kind: 'result', type: sec.type, item: r })}
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
