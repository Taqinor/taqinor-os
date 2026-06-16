import { useCallback, useEffect, useMemo, useState } from 'react'
import { Link } from 'react-router-dom'
import installationsApi from '../../api/installationsApi'
import {
  KWC_BANDS, TYPE_LABELS, EMPTY_PARC_FILTERS,
  buildParcParams, osmLink, geolocated, formatKwc,
} from '../../features/installations/parc'

// Parc installé (N8) — systèmes installés = chantiers réceptionnés (mise en
// service / clôturés), actifs au parc. Liste filtrable + vue « carte » légère.
//
// VUE CARTE : aucune dépendance carto lourde n'est ajoutée (pas de Leaflet ni
// Mapbox dans le projet). On dégrade proprement en une liste géographique avec,
// pour chaque système géolocalisé, un lien OpenStreetMap ouvrant le point.

export default function ParcPage() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [filters, setFilters] = useState(EMPTY_PARC_FILTERS)
  const [view, setView] = useState('liste') // 'liste' | 'carte'

  const queryParams = useMemo(() => buildParcParams(filters), [filters])

  const reload = useCallback(() =>
    installationsApi.getParc(queryParams)
      .then((r) => {
        const data = r.data
        setRows(Array.isArray(data) ? data : (data.results ?? []))
      })
      .catch(() => setRows([]))
      .finally(() => setLoading(false)), [queryParams])

  useEffect(() => { reload() }, [reload])

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))
  const dirty = Object.values(filters).some((v) => v !== '')

  const geoRows = useMemo(() => geolocated(rows), [rows])

  return (
    <div className="page">
      <div className="page-header">
        <div>
          <h1 className="page-title">Parc installé</h1>
          <div className="page-subtitle">{rows.length} système(s) installé(s)</div>
        </div>
        <div style={{ display: 'flex', gap: 6 }}>
          <button type="button"
                  className={`btn btn-sm ${view === 'liste' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setView('liste')}>Liste</button>
          <button type="button"
                  className={`btn btn-sm ${view === 'carte' ? 'btn-primary' : 'btn-outline'}`}
                  onClick={() => setView('carte')}>Carte</button>
        </div>
      </div>

      {/* ── Filtres ── */}
      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (référence, client, ville)…"
               value={filters.q} onChange={(e) => setF('q', e.target.value)}
               style={{ flex: '1 1 220px' }} />
        <input className="form-control" placeholder="Ville"
               value={filters.ville} onChange={(e) => setF('ville', e.target.value)}
               style={{ flex: '0 1 150px' }} />
        <input className="form-control" placeholder="Marque (composant)"
               value={filters.marque} onChange={(e) => setF('marque', e.target.value)}
               style={{ flex: '0 1 170px' }} />
        <select className="form-select" value={filters.type_installation}
                onChange={(e) => setF('type_installation', e.target.value)}>
          <option value="">Tous types</option>
          {Object.entries(TYPE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
        <select className="form-select" value={filters.band}
                onChange={(e) => setF('band', e.target.value)}>
          {KWC_BANDS.map((b) => <option key={b.value} value={b.value}>{b.label}</option>)}
        </select>
        <input className="form-control" placeholder="Année" type="number"
               value={filters.annee} onChange={(e) => setF('annee', e.target.value)}
               style={{ width: 100 }} />
        {dirty && (
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => setFilters(EMPTY_PARC_FILTERS)}>Réinitialiser</button>
        )}
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">
          Aucun système installé. Un chantier rejoint le parc dès sa mise en service.
        </p>
      ) : view === 'liste' ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Référence</th>
                <th>Client</th>
                <th className="m-hide">Ville</th>
                <th className="m-hide">Type</th>
                <th>Puissance</th>
                <th className="m-hide">Marques</th>
                <th className="m-hide">Réception</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((r) => (
                <tr key={r.id}>
                  <td>
                    <Link to={`/parc/${r.id}`}>{r.reference}</Link>
                  </td>
                  <td>{r.client_nom ?? '—'}</td>
                  <td className="m-hide">{r.site_ville ?? '—'}</td>
                  <td className="m-hide">
                    {TYPE_LABELS[r.type_installation] ?? r.type_installation ?? '—'}
                  </td>
                  <td>{formatKwc(r.puissance_installee_kwc)}</td>
                  <td className="m-hide">
                    {(r.marques && r.marques.length) ? r.marques.join(', ') : '—'}
                  </td>
                  <td className="m-hide">{r.date_reception ?? r.date_mise_en_service ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        // ── Vue carte (dégradée) : liste géographique avec lien OpenStreetMap ──
        <div>
          <p className="gen-hint" style={{ marginBottom: 10 }}>
            Carte géographique — {geoRows.length} système(s) géolocalisé(s).
            Cliquez sur « Ouvrir » pour situer le point sur OpenStreetMap.
          </p>
          {geoRows.length === 0 ? (
            <p className="gen-hint">Aucun système géolocalisé (coordonnées GPS manquantes).</p>
          ) : (
            <div className="table-wrap">
              <table className="data-table">
                <thead>
                  <tr>
                    <th>Référence</th>
                    <th>Client</th>
                    <th className="m-hide">Ville</th>
                    <th>Coordonnées</th>
                    <th>Carte</th>
                  </tr>
                </thead>
                <tbody>
                  {geoRows.map((r) => (
                    <tr key={r.id}>
                      <td><Link to={`/parc/${r.id}`}>{r.reference}</Link></td>
                      <td>{r.client_nom ?? '—'}</td>
                      <td className="m-hide">{r.site_ville ?? '—'}</td>
                      <td>{Number(r.gps_lat).toFixed(5)}, {Number(r.gps_lng).toFixed(5)}</td>
                      <td>
                        <a className="btn btn-sm btn-outline" target="_blank" rel="noreferrer"
                           href={osmLink(r.gps_lat, r.gps_lng)}>Ouvrir ↗</a>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  )
}
