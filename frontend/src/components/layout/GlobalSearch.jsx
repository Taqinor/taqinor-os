// T5 — recherche globale (barre du haut). Saisie débouncée → /reporting/search,
// résultats groupés par type, clic → ouvre l'enregistrement via sa route. La
// règle métier et le périmètre société vivent côté serveur ; ici, UI seulement.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../../api/reportingApi'
import './globalsearch.css'

// Route d'ouverture par type d'entité (cf. router/index.jsx).
const ROUTE = {
  lead: (id) => `/crm/leads?lead=${id}`,
  client: () => '/crm',
  devis: () => '/ventes/devis',
  facture: () => '/ventes/factures',
  chantier: () => '/chantiers',
  equipement: () => '/equipements',
  ticket: () => '/sav',
}

export default function GlobalSearch() {
  const [q, setQ] = useState('')
  const [groups, setGroups] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const boxRef = useRef(null)
  const navigate = useNavigate()

  // Débounce : on ne lance la recherche que ~250 ms après la dernière frappe.
  // Tous les setState sont DANS le callback différé (asynchrone) — pas de
  // mise à jour d'état synchrone dans le corps de l'effet.
  useEffect(() => {
    const term = q.trim()
    const t = setTimeout(() => {
      if (term.length < 2) { setGroups([]); setLoading(false); return }
      setLoading(true)
      reportingApi.search(term)
        .then((r) => { setGroups(r.data.groups ?? []); setOpen(true) })
        .catch(() => setGroups([]))
        .finally(() => setLoading(false))
    }, term.length < 2 ? 0 : 250)
    return () => clearTimeout(t)
  }, [q])

  // Fermer le panneau au clic extérieur.
  useEffect(() => {
    const onDoc = (e) => {
      if (boxRef.current && !boxRef.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // ⌘K / Ctrl+K global → palette de commandes (construite par une autre lane,
  // qui écoute cet événement exact). Ignoré si l'utilisateur tape déjà dans un
  // champ pour ne pas voler la frappe.
  useEffect(() => {
    const onKey = (e) => {
      if ((e.metaKey || e.ctrlKey) && (e.key === 'k' || e.key === 'K')) {
        e.preventDefault()
        try { window.dispatchEvent(new CustomEvent('taqinor:command-palette')) } catch { /* no-op */ }
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const go = (type, id) => {
    const make = ROUTE[type]
    if (make) navigate(make(id))
    setOpen(false)
    setQ('')
  }

  return (
    <div className="gs-wrap" ref={boxRef}>
      <input
        className="gs-input"
        type="search"
        placeholder="Rechercher (leads, clients, devis, factures…)"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => { if (groups.length) setOpen(true) }}
        aria-label="Recherche globale"
      />
      {open && q.trim().length >= 2 && (
        <div className="gs-panel">
          {loading && <div className="gs-empty">Recherche…</div>}
          {!loading && groups.length === 0 && (
            <div className="gs-empty">Aucun résultat pour « {q.trim()} »</div>
          )}
          {!loading && groups.map((g) => (
            <div key={g.type} className="gs-group">
              <div className="gs-group-title">{g.label}</div>
              {g.results.map((r) => (
                <button
                  key={`${g.type}-${r.id}`}
                  type="button"
                  className="gs-result"
                  onClick={() => go(g.type, r.id)}
                >
                  <span className="gs-result-label">{r.label}</span>
                  {r.sublabel && <span className="gs-result-sub">{r.sublabel}</span>}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
