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
import {
  filterActions, filterCreateActions, readRecentEntities, pushRecentEntity,
} from './commandActions'
// VX13 — ROUTE/TYPE_LABEL + recherche débouncée mutualisés avec GlobalSearch
// (barre du haut) : plus aucune table dupliquée (cf. lib/search/entityRoutes.js).
import { ROUTE, TYPE_LABEL, TYPE_ACCENT, useEntitySearch } from '../lib/search/entityRoutes'
// NTUX10 — quick-create universel : Lead/Client/Ticket SAV/Produit s'ouvrent
// en MODAL par-dessus l'écran courant (jamais une navigation) — remplace, dans
// la section « Créer » de la palette UNIQUEMENT, les entrées nav lead/client
// de CREATE_ACTIONS ci-dessus (Devis reste nav : écran dédié, cf.
// providers/shortcuts.js). Le raccourci clavier direct `c l`/`c c`
// (ShortcutsProvider, code totalement séparé) est inchangé.
import { filterQuickCreateTypes, openQuickCreate } from '../features/uxviews/quickcreate/quickCreateEvents'

// Ids CREATE_ACTIONS (commandActions.js, dérivés de CREATE_SHORTCUTS) dont la
// version MODAL (ci-dessus) remplace la version nav dans la palette.
const QUICK_CREATE_REPLACES_NAV_IDS = new Set(['c-l', 'c-c'])

export function CommandPalette() {
  const [open, setOpen] = useState(false)
  const [q, setQ] = useState('')
  const [active, setActive] = useState(0)
  const inputRef = useRef(null)
  const listRef = useRef(null)
  const navigate = useNavigate()

  const term = q.trim()
  // VX13 — recherche débouncée mutualisée (cf. lib/search/entityRoutes.js) ;
  // `enabled: open` préserve le comportement d'origine (aucune requête tant
  // que la palette est fermée). `failed` renommé `error` au point d'usage pour
  // ne rien changer au reste du composant.
  const { groups, loading, failed: error } = useEntitySearch(term, { enabled: open })
  const actions = useMemo(() => filterActions(term), [term])
  // VX220(b) — actions de CRÉATION, section dédiée « Créer » (jamais mélangée
  // à la navigation « Actions » ci-dessus).
  const createActions = useMemo(() => filterCreateActions(term), [term])
  // NTUX10 — quick-create MODAL (lead/client/ticket/produit), fusionné dans la
  // MÊME section « Créer » que `createActions` — jamais une section dupliquée.
  const quickCreateTypes = useMemo(() => filterQuickCreateTypes(term), [term])
  // Récents (entités ouvertes via la palette) relus à chaque ouverture — DÉRIVÉS
  // via useMemo, donc aucun setState synchrone dans un effet (règle lint).
  const recent = useMemo(() => (open ? readRecentEntities() : []), [open])

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
    // VX220(b) — « Créer » — section dédiée, jamais mélangée à « Actions ».
    // NTUX10 — fusionne les entrées nav restantes (Devis — écran dédié) avec
    // le quick-create MODAL (Lead/Client/Ticket SAV/Produit) dans CETTE MÊME
    // section, en excluant les doublons nav que le modal remplace.
    const navCreateActions = createActions.filter((a) => !QUICK_CREATE_REPLACES_NAV_IDS.has(a.id))
    const createRows = [
      ...navCreateActions.map((a) => ({ ...a, quickCreateType: undefined })),
      ...quickCreateTypes.map((t) => ({ id: `qc-${t.id}`, label: t.label, quickCreateType: t.id })),
    ]
    if (createRows.length) {
      const rows = createRows.map((a) => {
        const index = f.length
        f.push({ kind: 'create', action: a })
        return { ...a, index }
      })
      secs.push({ key: 'create', title: 'Créer', kind: 'create', rows })
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
  }, [actions, createActions, quickCreateTypes, recent, groups, term])

  const close = useCallback(() => {
    setOpen(false)
    setQ('')
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

  // À l'ouverture : focus l'input (les récents sont dérivés via useMemo).
  useEffect(() => {
    if (!open) return undefined
    const t = setTimeout(() => inputRef.current?.focus(), 30)
    return () => clearTimeout(t)
  }, [open])

  // VX13 — la recherche elle-même vit dans useEntitySearch (débounce ~250 ms,
  // cf. lib/search/entityRoutes.js) ; on garde ici SEULEMENT la remise à zéro
  // de la sélection clavier à chaque nouvelle requête (comportement
  // byte-identique à l'ancien effet local, qui remettait `active` à 0 au
  // lancement ET à l'arrivée de la réponse).
  // Remise à zéro de la sélection clavier quand la requête change — en phase
  // de rendu (patron React), pas dans un effet-setState.
  const [prevTerm, setPrevTerm] = useState(term)
  if (term !== prevTerm) {
    setPrevTerm(term)
    setActive(0)
  }

  // L'index actif peut dépasser la liste après un changement de résultats : on le
  // borne au point d'usage (rendu + Entrée) plutôt que via un setState en effet.
  const activeClamped = flat.length ? Math.min(active, flat.length - 1) : 0

  // Ouvre une cible quelconque de la liste aplatie.
  const activate = useCallback((entry) => {
    if (!entry) return
    // NTUX10 — une entrée « Créer » quick-create ouvre son MODAL par-dessus
    // l'écran courant (aucune navigation) ; les autres entrées « Créer »
    // (Devis — écran dédié) et « Actions » gardent le comportement nav existant.
    if (entry.kind === 'create' && entry.action.quickCreateType) {
      openQuickCreate(entry.action.quickCreateType)
    } else if (entry.kind === 'action' || entry.kind === 'create') {
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
      if (flat[activeClamped]) activate(flat[activeClamped])
    }
    // Échap est géré par le Dialog (onOpenChange) → close().
  }, [flat, activeClamped, activate])

  // Garde l'élément actif visible.
  useEffect(() => {
    if (!open || !listRef.current) return
    const el = listRef.current.querySelector('[data-active="true"]')
    el?.scrollIntoView({ block: 'nearest' })
  }, [activeClamped, open])

  const showSearchStates = term.length >= 2

  return (
    <Dialog open={open} onOpenChange={(v) => (v ? setOpen(true) : close())}>
      <DialogContent
        className="cmdk-content"
        variant="command"
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
                if (sec.kind === 'action' || sec.kind === 'create') {
                  return (
                    <button
                      key={`${sec.kind}-${r.id}`}
                      type="button"
                      className="cmdk-item"
                      data-active={i === activeClamped ? 'true' : 'false'}
                      onMouseMove={() => setActive(i)}
                      onClick={() => activate({ kind: sec.kind, action: r })}
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
                      data-active={i === activeClamped ? 'true' : 'false'}
                      onMouseMove={() => setActive(i)}
                      onClick={() => activate({ kind: 'recent', entity: r })}
                    >
                      {/* VX13 — pastille d'accent du module d'origine (VX8). */}
                      {TYPE_ACCENT[r.type] && (
                        <span
                          className="cmdk-item-accent"
                          style={{ '--module-accent': `var(--module-accent-${TYPE_ACCENT[r.type]})` }}
                          aria-hidden="true"
                        />
                      )}
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
                    data-active={i === activeClamped ? 'true' : 'false'}
                    onMouseMove={() => setActive(i)}
                    onClick={() => activate({ kind: 'result', type: sec.type, item: r })}
                  >
                    {/* VX13 — pastille d'accent du module d'origine (VX8). */}
                    {TYPE_ACCENT[sec.type] && (
                      <span
                        className="cmdk-item-accent"
                        style={{ '--module-accent': `var(--module-accent-${TYPE_ACCENT[sec.type]})` }}
                        aria-hidden="true"
                      />
                    )}
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
