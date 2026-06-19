// T5 — recherche globale (barre du haut). Saisie débouncée → /reporting/search,
// résultats groupés par type, clic → ouvre l'enregistrement via sa route. La
// règle métier et le périmètre société vivent côté serveur ; ici, UI seulement.
import { useEffect, useMemo, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Search } from 'lucide-react'
import reportingApi from '../../api/reportingApi'

// Route d'ouverture par type d'entité (cf. router/index.jsx).
const ROUTE = {
  lead: (id) => `/crm/leads?lead=${id}`,
  client: () => '/crm',
  devis: () => '/ventes/devis',
  facture: () => '/ventes/factures',
  chantier: () => '/chantiers',
  equipement: () => '/equipements',
  ticket: () => '/sav',
  bon_commande: () => '/ventes/bons-commande',
  contrat: () => '/sav/contrats',
  dossier: () => '/chantiers',
}

// Route de LISTE par type, filtrée par la requête (lien « voir tout »). On reste
// sur la route d'ouverture du type quand aucune liste filtrable n'existe.
const LIST_ROUTE = {
  lead: (q) => `/crm/leads?q=${encodeURIComponent(q)}`,
  client: (q) => `/crm?q=${encodeURIComponent(q)}`,
  devis: (q) => `/ventes/devis?q=${encodeURIComponent(q)}`,
  facture: (q) => `/ventes/factures?q=${encodeURIComponent(q)}`,
  chantier: (q) => `/chantiers?q=${encodeURIComponent(q)}`,
  equipement: (q) => `/equipements?q=${encodeURIComponent(q)}`,
  ticket: (q) => `/sav?q=${encodeURIComponent(q)}`,
  bon_commande: (q) => `/ventes/bons-commande?q=${encodeURIComponent(q)}`,
  contrat: (q) => `/sav/contrats?q=${encodeURIComponent(q)}`,
}

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
  const [groups, setGroups] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  // L11 — distinguer un échec réseau d'un vrai « aucun résultat ».
  const [failed, setFailed] = useState(false)
  // L9 — mémoire des recherches récentes (affichée quand la boîte vide a le focus).
  const [recent, setRecent] = useState(readRecent)
  // L9 — navigation clavier : index de l'item surligné dans la liste aplatie.
  const [activeIndex, setActiveIndex] = useState(-1)
  // L12 — sur mobile la boîte est repliée derrière une icône qui se déplie.
  const [expanded, setExpanded] = useState(false)
  const boxRef = useRef(null)
  const inputRef = useRef(null)
  const navigate = useNavigate()

  const term = q.trim()

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

  // Débounce : on ne lance la recherche que ~250 ms après la dernière frappe.
  useEffect(() => {
    const t = setTimeout(() => {
      if (term.length < 2) {
        setGroups([]); setLoading(false); setFailed(false); setActiveIndex(-1); return
      }
      setLoading(true)
      setFailed(false)
      setActiveIndex(-1)
      reportingApi.search(term)
        .then((r) => { setGroups(r.data.groups ?? []); setOpen(true) })
        .catch(() => { setGroups([]); setFailed(true); setOpen(true) })
        .finally(() => setLoading(false))
    }, term.length < 2 ? 0 : 250)
    return () => clearTimeout(t)
  }, [q]) // eslint-disable-line react-hooks/exhaustive-deps

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
                  type="button"
                  role="option"
                  aria-selected={activeIndex === r.index}
                  className={`gs-result${activeIndex === r.index ? ' gs-result-active' : ''}`}
                  onMouseEnter={() => setActiveIndex(r.index)}
                  onClick={() => go(g.type, r.id)}
                >
                  <span className="gs-result-label">{r.label}</span>
                  {r.sublabel && <span className="gs-result-sub">{r.sublabel}</span>}
                </button>
              ))}
              {g.moreRow && (
                <button
                  type="button"
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
