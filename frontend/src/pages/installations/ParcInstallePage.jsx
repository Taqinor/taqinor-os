// N8 — Parc installé : base canonique des systèmes installés (chantiers
// réceptionnés). Liste filtrable (client, ville, marque, tranche de puissance,
// année d'installation) + vue « carte » par liens GPS. La carte à tuiles
// interactive est différée (nécessiterait une nouvelle dépendance, leaflet).
// N10 — un clic ouvre la fiche système (InstallationDetail), le hub par actif.
import { useEffect, useMemo, useState } from 'react'
import installationsApi from '../../api/installationsApi'
import importApi, { downloadXlsx } from '../../api/importApi'
import { TYPE_LABELS } from '../../features/installations/statuses'
import InstallationDetail from './InstallationDetail'

const installYear = (it) => {
  const iso = it.date_reception || it.date_mise_en_service
  if (!iso) return null
  const y = parseInt(String(iso).slice(0, 4), 10)
  return Number.isNaN(y) ? null : y
}

const capacityBand = (kwc) => {
  const v = Number(kwc) || 0
  if (v <= 0) return null
  if (v < 3) return '< 3 kWc'
  if (v < 10) return '3–10 kWc'
  if (v < 50) return '10–50 kWc'
  return '≥ 50 kWc'
}

const bomMarques = (it) =>
  [...new Set((it.bom ?? []).map((l) => l.marque).filter(Boolean))]

export default function ParcInstallePage() {
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(true)
  const [selected, setSelected] = useState(null)
  const [view, setView] = useState('liste')
  const [filters, setFilters] = useState({ q: '', ville: '', marque: '', band: '', annee: '' })

  const reload = () => {
    // Récupère toutes les pages des systèmes réceptionnés (?parc=1).
    const all = []
    const fetchPage = (page) =>
      installationsApi.getInstallations({ parc: 1, page }).then((r) => {
        const d = r.data
        if (Array.isArray(d)) { all.push(...d); setItems([...all]); setLoading(false); return }
        all.push(...(d.results ?? []))
        if (d.next && page < 50) return fetchPage(page + 1)
        setItems([...all]); setLoading(false)
      })
    fetchPage(1).catch(() => setLoading(false))
  }
  useEffect(() => { reload() }, [])

  const setF = (k, v) => setFilters((f) => ({ ...f, [k]: v }))

  const villeOptions = useMemo(
    () => [...new Set(items.map((i) => i.site_ville).filter(Boolean))].sort(), [items])
  const marqueOptions = useMemo(
    () => [...new Set(items.flatMap(bomMarques))].sort(), [items])
  const anneeOptions = useMemo(
    () => [...new Set(items.map(installYear).filter(Boolean))].sort((a, b) => b - a), [items])

  const rows = useMemo(() => {
    const q = filters.q.trim().toLowerCase()
    return items.filter((it) => {
      if (filters.ville && it.site_ville !== filters.ville) return false
      if (filters.marque && !bomMarques(it).includes(filters.marque)) return false
      if (filters.band && capacityBand(it.puissance_installee_kwc) !== filters.band) return false
      if (filters.annee && String(installYear(it)) !== String(filters.annee)) return false
      if (!q) return true
      return (it.reference ?? '').toLowerCase().includes(q)
        || (it.client_nom ?? '').toLowerCase().includes(q)
        || (it.site_ville ?? '').toLowerCase().includes(q)
    })
  }, [items, filters])

  const located = rows.filter((it) => it.gps_lat && it.gps_lng)

  return (
    <div className="page">
      <div className="page-header">
        <h1 className="page-title">Parc installé</h1>
        <div className="page-subtitle">{rows.length} système(s) installé(s)</div>
        <div className="page-header-actions" style={{ display: 'flex', gap: 8 }}>
          <button type="button" className="btn btn-sm btn-outline"
                  onClick={() => importApi.exportList('chantiers', rows.map((r) => r.id))
                    .then((r) => downloadXlsx(r.data, 'parc-installe.xlsx')).catch(() => {})}>
            ⬇ Exporter Excel
          </button>
          <div className="fb-pills" role="group" aria-label="Changer de vue">
            <button type="button" className={`fb-pill${view === 'liste' ? ' fb-pill-active' : ''}`}
                    onClick={() => setView('liste')}>Liste</button>
            <button type="button" className={`fb-pill${view === 'carte' ? ' fb-pill-active' : ''}`}
                    onClick={() => setView('carte')}>Carte</button>
          </div>
        </div>
      </div>

      <div className="filter-bar" style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: 12 }}>
        <input className="form-control" placeholder="Rechercher (réf, client, ville)…"
               value={filters.q} onChange={(e) => setF('q', e.target.value)} style={{ flex: '1 1 200px' }} />
        <select className="form-select" value={filters.ville} onChange={(e) => setF('ville', e.target.value)}>
          <option value="">Toutes les villes</option>
          {villeOptions.map((v) => <option key={v} value={v}>{v}</option>)}
        </select>
        <select className="form-select" value={filters.marque} onChange={(e) => setF('marque', e.target.value)}>
          <option value="">Toutes les marques</option>
          {marqueOptions.map((m) => <option key={m} value={m}>{m}</option>)}
        </select>
        <select className="form-select" value={filters.band} onChange={(e) => setF('band', e.target.value)}>
          <option value="">Toutes puissances</option>
          {['< 3 kWc', '3–10 kWc', '10–50 kWc', '≥ 50 kWc'].map((b) => <option key={b} value={b}>{b}</option>)}
        </select>
        <select className="form-select" value={filters.annee} onChange={(e) => setF('annee', e.target.value)}>
          <option value="">Toutes années</option>
          {anneeOptions.map((y) => <option key={y} value={y}>{y}</option>)}
        </select>
      </div>

      {loading ? (
        <p className="gen-hint">Chargement…</p>
      ) : rows.length === 0 ? (
        <p className="gen-hint">Aucun système installé. Un chantier rejoint le parc dès qu'il atteint « Réceptionné ».</p>
      ) : view === 'liste' ? (
        <div className="table-wrap">
          <table className="data-table">
            <thead>
              <tr>
                <th>Référence</th><th>Client</th><th>Ville</th>
                <th>Puissance</th><th>Type</th><th>Année</th><th>Installateur</th>
              </tr>
            </thead>
            <tbody>
              {rows.map((it) => (
                <tr key={it.id} onClick={() => setSelected(it)} style={{ cursor: 'pointer' }}>
                  <td>{it.reference}</td>
                  <td>{it.client_nom ?? '—'}</td>
                  <td>{it.site_ville ?? '—'}</td>
                  <td>{it.puissance_installee_kwc ? `${it.puissance_installee_kwc} kWc` : '—'}</td>
                  <td>{TYPE_LABELS[it.type_installation] ?? '—'}</td>
                  <td>{installYear(it) ?? '—'}</td>
                  <td>{it.technicien_nom ?? '—'}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      ) : (
        <div>
          <p className="gen-hint">
            {located.length} système(s) géolocalisé(s). Cliquez « Ouvrir sur la carte »
            pour visualiser un site (la carte à tuiles intégrée sera ajoutée ultérieurement).
          </p>
          <div className="table-wrap">
            <table className="data-table">
              <thead>
                <tr><th>Référence</th><th>Client</th><th>Ville</th><th>GPS</th><th></th></tr>
              </thead>
              <tbody>
                {located.map((it) => (
                  <tr key={it.id}>
                    <td><button type="button" className="btn btn-sm btn-outline" onClick={() => setSelected(it)}>{it.reference}</button></td>
                    <td>{it.client_nom ?? '—'}</td>
                    <td>{it.site_ville ?? '—'}</td>
                    <td>{it.gps_lat}, {it.gps_lng}</td>
                    <td>
                      <a className="btn btn-sm btn-outline" target="_blank" rel="noopener"
                         href={`https://www.openstreetmap.org/?mlat=${it.gps_lat}&mlon=${it.gps_lng}#map=17/${it.gps_lat}/${it.gps_lng}`}>
                        Ouvrir sur la carte
                      </a>
                    </td>
                  </tr>
                ))}
                {located.length === 0 && (
                  <tr><td colSpan={5} className="gen-hint">Aucun système géolocalisé.</td></tr>
                )}
              </tbody>
            </table>
          </div>
        </div>
      )}

      {selected && (
        <InstallationDetail installation={selected} onClose={() => setSelected(null)}
                            onSaved={() => { reload(); setSelected(null) }} />
      )}
    </div>
  )
}
