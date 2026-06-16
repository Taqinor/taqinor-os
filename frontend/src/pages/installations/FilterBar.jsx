import { useMemo } from 'react'
import {
  EMPTY_FILTERS,
  INSTALLATION_STATUSES,
  STATUS_LABELS,
  TYPE_LABELS,
  REGIME_8221_LABELS,
} from '../../features/installations/statuses'

// Barre de recherche/filtres partagée par les vues (façon Odoo).
// `items` = liste NON filtrée, pour dériver les techniciens disponibles.
export default function FilterBar({ filters, setFilters, items }) {
  const techniciens = useMemo(() => {
    const set = new Set()
    for (const it of items ?? []) {
      if (it.technicien_nom) set.add(it.technicien_nom)
    }
    return [...set].sort((a, b) => a.localeCompare(b, 'fr'))
  }, [items])

  const set = (key) => (e) => setFilters({ ...filters, [key]: e.target.value })
  const setAnnule = (value) => setFilters({ ...filters, annule: value })

  const isDirty = Object.keys(EMPTY_FILTERS).some(k => filters[k] !== EMPTY_FILTERS[k])

  return (
    <div className="fb-bar">
      <input
        className="search-input fb-search"
        type="search"
        placeholder="Rechercher référence, client, ville…"
        value={filters.q}
        onChange={set('q')}
      />

      <select className="search-input fb-select" value={filters.statut} onChange={set('statut')}
              aria-label="Filtrer par statut">
        <option value="">Tous les statuts</option>
        {INSTALLATION_STATUSES.map(k => (
          <option key={k} value={k}>{STATUS_LABELS[k]}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.type_installation} onChange={set('type_installation')}
              aria-label="Filtrer par type d'installation">
        <option value="">Tous les types</option>
        {Object.entries(TYPE_LABELS).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.technicien} onChange={set('technicien')}
              aria-label="Filtrer par technicien">
        <option value="">Tous les techniciens</option>
        {techniciens.map(t => (
          <option key={t} value={t}>{t}</option>
        ))}
      </select>

      <select className="search-input fb-select" value={filters.regime} onChange={set('regime')}
              aria-label="Filtrer par régime loi 82-21">
        <option value="">Tous les régimes</option>
        {Object.entries(REGIME_8221_LABELS).map(([k, v]) => (
          <option key={k} value={k}>{v}</option>
        ))}
      </select>

      <button
        type="button"
        className={`fb-pill${filters.art33 === 'seuls' ? ' fb-pill-active' : ''}`}
        onClick={() => setFilters({ ...filters, art33: filters.art33 === 'seuls' ? '' : 'seuls' })}
        title="Régularisation Article 33"
      >
        Art. 33
      </button>

      <div className="fb-pills" role="group" aria-label="Filtre chantiers annulés">
        <button
          type="button"
          className={`fb-pill${filters.annule === 'avec' ? ' fb-pill-active' : ''}`}
          onClick={() => setAnnule('avec')}
        >
          Avec annulés
        </button>
        <button
          type="button"
          className={`fb-pill${filters.annule === 'sans' ? ' fb-pill-active' : ''}`}
          onClick={() => setAnnule('sans')}
        >
          Sans annulés
        </button>
        <button
          type="button"
          className={`fb-pill${filters.annule === 'seuls' ? ' fb-pill-active' : ''}`}
          onClick={() => setAnnule('seuls')}
        >
          Annulés seuls
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
