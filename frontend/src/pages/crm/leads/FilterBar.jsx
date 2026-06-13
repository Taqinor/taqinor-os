import { useMemo } from 'react'
import {
  EMPTY_FILTERS,
  CANAL_LABELS,
  PRIORITE_LABELS,
  tagList,
} from '../../../features/crm/stages'

// Barre de recherche/filtres partagée par les quatre vues (façon Odoo).
// `leads` = liste NON filtrée, pour dériver les options disponibles.
export default function FilterBar({ filters, setFilters, leads }) {
  const owners = useMemo(() => {
    const set = new Set()
    for (const l of leads ?? []) {
      if (l.owner_nom) set.add(l.owner_nom)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [leads])

  const tags = useMemo(() => {
    const set = new Set()
    for (const l of leads ?? []) {
      for (const t of tagList(l)) set.add(t)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [leads])

  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value })
  const setPerdus = (value) => setFilters({ ...filters, perdus: value })

  const isDirty = Object.keys(EMPTY_FILTERS).some(k => filters[k] !== EMPTY_FILTERS[k])

  return (
    <div className="fb-bar">
      <input
        className="search-input fb-search"
        type="search"
        placeholder="Rechercher nom, téléphone, email…"
        value={filters.q}
        onChange={set('q')}
      />

      <select className="search-input fb-select" value={filters.canal} onChange={set('canal')}
              aria-label="Filtrer par canal">
        <option value="">Tous les canaux</option>
        {Object.entries(CANAL_LABELS).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.owner} onChange={set('owner')}
              aria-label="Filtrer par responsable">
        <option value="">Tous les responsables</option>
        {owners.map(o => (
          <option key={o} value={o}>{o}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.priorite} onChange={set('priorite')}
              aria-label="Filtrer par priorité">
        <option value="">Toutes priorités</option>
        {Object.entries(PRIORITE_LABELS).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.tag} onChange={set('tag')}
              aria-label="Filtrer par tag">
        <option value="">Tous les tags</option>
        {tags.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <div className="fb-pills" role="group" aria-label="Filtre leads perdus">
        <button
          type="button"
          className={`fb-pill${filters.perdus === 'avec' ? ' fb-pill-active' : ''}`}
          onClick={() => setPerdus('avec')}
        >
          Avec perdus
        </button>
        <button
          type="button"
          className={`fb-pill${filters.perdus === 'sans' ? ' fb-pill-active' : ''}`}
          onClick={() => setPerdus('sans')}
        >
          Sans perdus
        </button>
        <button
          type="button"
          className={`fb-pill${filters.perdus === 'seuls' ? ' fb-pill-active' : ''}`}
          onClick={() => setPerdus('seuls')}
        >
          Perdus seuls
        </button>
      </div>

      {isDirty && (
        <button
          type="button"
          className="fb-clear"
          onClick={() => setFilters(EMPTY_FILTERS)}
        >
          Effacer les filtres
        </button>
      )}
    </div>
  )
}
