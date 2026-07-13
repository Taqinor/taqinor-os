// T5 — recherche globale (barre du haut). Saisie débouncée → /reporting/search,
// résultats groupés par type, clic → ouvre l'enregistrement via sa route. La
// règle métier et le périmètre société vivent côté serveur ; ici, UI seulement.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
// VX13 — ROUTE/LIST_ROUTE + recherche débouncée mutualisés avec CommandPalette
// (⌘K) : plus aucune table dupliquée (cf. lib/search/entityRoutes.js).
import { ROUTE, LIST_ROUTE, TYPE_ACCENT, useEntitySearch } from '../../lib/search/entityRoutes'
import { useActiveDescendant } from '../../hooks/useActiveDescendant'

// Mémoire des recherches récentes (localStorage, effacée à la déconnexion).
const RECENT_KEY = 'taqinor.search.recent'
const RECENT_MAX = 6

function readRecent() {
  try {
    const raw = window.localStorage.getItem(RECENT_KEY)
    const arr = raw ? JSON.parse(raw) : []
    return Array.isArray(arr) ? arr.slice(0, RECENT_MAX) : []
  } catch {
    return []
  }
}

function writeRecent(items) {
  try {
    window.localStorage.setItem(RECENT_KEY, JSON.stringify(items.slice(0, RECENT_MAX)))
  } catch { /* stockage indisponible : on ignore */ }
}

export default function GlobalSearch() {
  const [q, setQ] = useState('')
  const [open, setOpen] = useState(false)
  // L9 — mémoire des recherches récentes (affichée quand la boîte vide a le focus).
  const [recent, setRecent] = useState(readRecent)
  // L9 — navigation clavier : index de l'item surligné dans la liste aplatie.
  const [activeIndex, setActiveIndex] = useState(-1)
  // L12 — sur mobile la boîte est repliée derrière une icône qui se déplie.
  const [expanded, setExpanded] = useState(false)
  const boxRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()
  // VX191 — `aria-activedescendant` : flécher au clavier annonçait déjà le
  // style visuel (`gs-result-active`) mais rien au lecteur d'écran.
  const { getOptionId, activeId } = useActiveDescendant(activeIndex)

  const term = q.trim()
  // VX13 — recherche débouncée mutualisée (cf. lib/search/entityRoutes.js) ;
  // L11 — `failed` distingue un échec réseau d'un vrai « aucun résultat ».
  const { groups, loading, failed } = useEntitySearch(term)

  // Liste APLATIE des cibles ouvrables (résultats + liens « voir tout ») pour la
  // navigation clavier, en portant déjà l'index plat sur chaque élément de
  // rendu. Quand la boîte vide est focalisée, ce sont les récents. On dérive
  // TOUT du rendu (pas de compteur muté pendant le rendu).
  const { flat, recentRows, groupRows } = useMemo(() => {
    if (term.length < 2) {
      const rows = recent.map((value, i) => ({ index: i, value }))
      return {
        flat: rows.map((r) => ({ kind: 'recent', value: r.value })),
        recentRows: rows,
        groupRows: [],
      }
    }
    const flatList = []
    const grows = groups.map((g) => {
      const results = g.results.map((r) => {
        const index = flatList.length
        flatList.push({ kind: 'result', type: g.type, id: r.id })
        return { ...r, index }
      })
      let moreRow = null
      if (g.more && LIST_ROUTE[g.type]) {
        const index = flatList.length
        flatList.push({ kind: 'more', type: g.type })
        moreRow = {
          index,
          text: g.more_count ? `+${g.more_count} autres` : 'Voir tout',
        }
      }
      return { type: g.type, label: g.label, results, moreRow }
    })
    return { flat: flatList, recentRows: [], groupRows: grows }
  }, [term, recent, groups])

  // VX13 — la recherche elle-même vit dans useEntitySearch (débounce ~250 ms,
  // cf. lib/search/entityRoutes.js) ; ici on garde SEULEMENT les effets propres
  // à GlobalSearch : réinitialiser la sélection clavier à chaque nouvelle
  // requête, et rouvrir le panneau quand une réponse (résultats OU échec) est
  // disponible — comportement byte-identique à l'ancien effet local.
  // Réinitialise la sélection clavier quand la requête change — en phase de
  // rendu (patron React « ajuster l'état quand une valeur change »), pas dans
  // un effet-setState.
  const [prevTerm, setPrevTerm] = useState(term)
  if (term !== prevTerm) {
    setPrevTerm(term)
    setActiveIndex(-1)
  }

  useEffect(() => {
    // Rouvre le panneau à l'ARRIVÉE d'une réponse asynchrone (résultats/échec) :
    // réaction à un état externe, pas un état dérivable en rendu.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    if (term.length >= 2 && !loading) setOpen(true)
  }, [groups, failed, loading, term])

  // Fermer le panneau au clic extérieur (et replier l'input mobile).
  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) {
        setOpen(false)
        setExpanded(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // Efface la mémoire des recherches à la déconnexion (autre onglet inclus).
  useEffect(() => {
    const onStorage = (e) => {
      if (e.key === RECENT_KEY) setRecent(readRecent())
    }
    window.addEventListener('storage', onStorage)
    return () => window.removeEventListener('storage', onStorage)
  }, [])

  // NB : le raccourci clavier ⌘K / Ctrl+K est géré par la CommandPalette
  // (autre lane) pour éviter un double gestionnaire (ouvre-puis-referme).

  const rememberAndClose = (label) => {
    if (label) {
      const next = [label, ...recent.filter((r) => r !== label)].slice(0, RECENT_MAX)
      setRecent(next)
      writeRecent(next)
    }
    setOpen(false)
    setQ('')
    setExpanded(false)
  }

  const go = (type, id) => {
    const make = ROUTE[type]
    if (make) navigate(make(id))
    rememberAndClose(term)
  }

  // « Voir tout » : ouvre la liste du type filtrée par la requête.
  const goAll = (type) => {
    const make = LIST_ROUTE[type]
    if (make) navigate(make(term))
    rememberAndClose(term)
  }

  // Relance une recherche récente (clic ou Entrée sur un récent).
  const runRecent = (value) => {
    setQ(value)
    setOpen(true)
    inputRef.current?.focus()
  }

  // Active (ouvre) l'item à l'index donné dans la liste aplatie.
  const activate = (idx) => {
    const item = flat[idx]
    if (!item) return
    if (item.kind === 'recent') runRecent(item.value)
    else if (item.kind === 'more') goAll(item.type)
    else go(item.type, item.id)
  }

  // L9 — navigation clavier : ↑/↓ déplacent, Entrée ouvre, Échap ferme.
  const onKeyDown = (e) => {
    if (e.key === 'Escape') { setOpen(false); setExpanded(false); inputRef.current?.blur(); return }
    if (e.key === 'ArrowDown') {
      e.preventDefault()
      setOpen(true)
      setActiveIndex((i) => (flat.length ? (i + 1) % flat.length : -1))
    } else if (e.key === 'ArrowUp') {
      e.preventDefault()
      setActiveIndex((i) => (flat.length ? (i - 1 + flat.length) % flat.length : -1))
    } else if (e.key === 'Enter') {
      if (activeIndex >= 0 && activeIndex < flat.length) {
        e.preventDefault()
        activate(activeIndex)
      }
    }
  }

  const onFocus = () => {
    // Boîte vide focalisée → propose les récents ; sinon rouvre les résultats.
    if (term.length < 2) { if (recent.length) setOpen(true) }
    else if (groups.length || failed) setOpen(true)
  }

  const showRecent = term.length < 2 && recentRows.length > 0

  return (
    <div className={`gs-wrap${expanded ? ' gs-wrap-expanded' : ''}`} ref={boxRef}>
      {/* L12 — déclencheur mobile : icône loupe qui déplie l'input. */}
      <button
        type="button"
        className="gs-mobile-toggle"
        aria-label="Ouvrir la recherche"
        onClick={() => { setExpanded(true); setTimeout(() => inputRef.current?.focus(), 0) }}
      >
        <Search size={18} aria-hidden="true" />
      </button>
      <input
        ref={inputRef}
        className="gs-input"
        type="search"
        placeholder="Rechercher (leads, clients, devis, factures…)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={onFocus}
        onKeyDown={onKeyDown}
        role="combobox"
        aria-expanded={open}
        aria-controls="gs-panel"
        aria-autocomplete="list"
        aria-activedescendant={activeId}
        aria-label="Recherche globale"
        autoComplete="off"
      />
      {open && (showRecent || term.length >= 2) && (
        <div className="gs-panel" id="gs-panel" role="listbox">
          {/* Recherches récentes (boîte vide). */}
          {showRecent && (
            <div className="gs-group">
              <div className="gs-group-title">Recherches récentes</div>
              {recentRows.map(({ value, index }) => (
                <button
                  key={`recent-${value}`}
                  id={getOptionId(index)}
                  type="button"
                  role="option"
                  aria-selected={activeIndex === index}
                  className={`gs-result${activeIndex === index ? ' gs-result-active' : ''}`}
                  onMouseEnter={() => setActiveIndex(index)}
                  onClick={() => runRecent(value)}
                >
                  <span className="gs-result-label">{value}</span>
                </button>
              ))}
            </div>
          )}

          {/* État de recherche. */}
          {term.length >= 2 && loading && <div className="gs-empty">Recherche…</div>}
          {term.length >= 2 && !loading && failed && (
            <div className="gs-empty gs-error" role="alert">
              Recherche indisponible, réessayez
            </div>
          )}
          {term.length >= 2 && !loading && !failed && groupRows.length === 0 && (
            <div className="gs-empty">Aucun résultat pour « {term} »</div>
          )}
          {term.length >= 2 && !loading && !failed && groupRows.map((g) => (
            <div key={g.type} className="gs-group">
              <div className="gs-group-title">{g.label}</div>
              {g.results.map((r) => (
                <button
                  key={`${g.type}-${r.id}`}
                  id={getOptionId(r.index)}
                  type="button"
                  role="option"
                  aria-selected={activeIndex === r.index}
                  className={`gs-result${activeIndex === r.index ? ' gs-result-active' : ''}`}
                  onMouseEnter={() => setActiveIndex(r.index)}
                  onClick={() => go(g.type, r.id)}
                >
                  {/* VX13 — pastille d'accent du module d'origine (VX8). */}
                  {TYPE_ACCENT[g.type] && (
                    <span
                      className="gs-result-accent"
                      style={{ '--module-accent': `var(--module-accent-${TYPE_ACCENT[g.type]})` }}
                      aria-hidden="true"
                    />
                  )}
                  <span className="gs-result-label">{r.label}</span>
                  {r.sublabel && <span className="gs-result-sub">{r.sublabel}</span>}
                </button>
              ))}
              {g.moreRow && (
                <button
                  type="button"
                  id={getOptionId(g.moreRow.index)}
                  role="option"
                  aria-selected={activeIndex === g.moreRow.index}
                  className={`gs-more${activeIndex === g.moreRow.index ? ' gs-result-active' : ''}`}
                  onMouseEnter={() => setActiveIndex(g.moreRow.index)}
                  onClick={() => goAll(g.type)}
                >
                  {g.moreRow.text}
                </button>
              )}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
