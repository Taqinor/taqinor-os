// Recherche globale (T5) — composant autonome destiné au Header partagé.
// Interroge /crm/search/?q= (debounce) et affiche les résultats groupés par
// type avec navigation directe via la route fournie par le serveur.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../api/crmApi'
import './globalsearch.css'

export default function GlobalSearch() {
  const navigate = useNavigate()
  const [q, setQ] = useState('')
  const [groups, setGroups] = useState([])
  const [open, setOpen] = useState(false)
  const [loading, setLoading] = useState(false)
  const ref = useRef(null)

  // Ferme au clic extérieur.
  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  // Recherche debouncée (250 ms). Ignore les requêtes < 2 caractères.
  useEffect(() => {
    const term = q.trim()
    if (term.length < 2) {
      // Reporté (setTimeout 0) pour ne pas appeler setState dans le corps
      // synchrone de l'effet.
      const clear = setTimeout(() => setGroups([]), 0)
      return () => clearTimeout(clear)
    }
    const t = setTimeout(() => {
      setLoading(true)
      crmApi.globalSearch(term)
        .then((r) => { setGroups(r.data.groups ?? []); setOpen(true) })
        .catch(() => setGroups([]))
        .finally(() => setLoading(false))
    }, 250)
    return () => clearTimeout(t)
  }, [q])

  const go = (route) => {
    setOpen(false)
    setQ('')
    if (route) navigate(route)
  }

  const hasResults = groups.some((g) => g.items?.length)

  return (
    <div className="gs-wrap" ref={ref}>
      <input
        type="search"
        className="gs-input"
        placeholder="Rechercher partout…"
        value={q}
        onChange={(e) => setQ(e.target.value)}
        onFocus={() => { if (groups.length) setOpen(true) }}
        aria-label="Recherche globale"
      />
      {open && q.trim().length >= 2 && (
        <div className="gs-results" role="listbox">
          {loading && <div className="gs-empty">Recherche…</div>}
          {!loading && !hasResults && (
            <div className="gs-empty">Aucun résultat</div>
          )}
          {!loading && groups.map((g) => (
            g.items?.length ? (
              <div key={g.type} className="gs-group">
                <div className="gs-group-label">{g.label}</div>
                {g.items.map((it) => (
                  <button
                    key={`${g.type}-${it.id}`}
                    type="button"
                    className="gs-item"
                    onClick={() => go(it.route)}
                  >
                    {it.label}
                  </button>
                ))}
              </div>
            ) : null
          ))}
        </div>
      )}
    </div>
  )
}
