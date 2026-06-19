import { useEffect, useMemo, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../api/reportingApi'
import MapView from '../components/MapView'

// N85 — Vue carte : leads, chantiers, systèmes installés et visites prévues sur
// une carte (Leaflet / OpenStreetMap), filtrables par type ET par statut.
// Cliquer un marqueur ouvre la fiche correspondante. Toutes les données sont
// bornées à la société de l'utilisateur (filtrage serveur).

const TYPES = [
  { key: 'lead', label: 'Leads', color: '#2563eb' },
  { key: 'chantier', label: 'Chantiers', color: '#ea580c' },
  { key: 'installe', label: 'Systèmes installés', color: '#16a34a' },
  { key: 'visite', label: 'Visites prévues', color: '#7c3aed' },
]
const COLOR = Object.fromEntries(TYPES.map((t) => [t.key, t.color]))

export default function CartePage() {
  const navigate = useNavigate()
  const [points, setPoints] = useState([])
  const [counts, setCounts] = useState({})
  const [loading, setLoading] = useState(true)
  const [err, setErr] = useState('')
  // Types masqués (clic sur la pastille pour basculer).
  const [hidden, setHidden] = useState(() => new Set())
  // Filtre statut (côté client : la liste des statuts dépend des points reçus).
  const [statut, setStatut] = useState('')

  useEffect(() => {
    let alive = true
    setLoading(true)
    reportingApi.getGeoPoints()
      .then((r) => {
        if (!alive) return
        setPoints(r.data.points || [])
        setCounts(r.data.counts || {})
      })
      .catch(() => { if (alive) setErr('Carte indisponible.') })
      .finally(() => { if (alive) setLoading(false) })
    return () => { alive = false }
  }, [])

  const toggleType = (k) => setHidden((prev) => {
    const next = new Set(prev)
    next.has(k) ? next.delete(k) : next.add(k)
    return next
  })

  // Statuts disponibles (clé → libellé), dérivés des points visibles par type.
  const statutOptions = useMemo(() => {
    const map = new Map()
    points.forEach((p) => {
      if (hidden.has(p.type)) return
      if (p.statut && !map.has(p.statut)) {
        map.set(p.statut, p.statut_label || p.statut)
      }
    })
    return Array.from(map, ([value, label]) => ({ value, label }))
      .sort((a, b) => a.label.localeCompare(b.label, 'fr'))
  }, [points, hidden])

  // Marqueurs visibles, colorés par type, avec un libellé de statut en popup.
  const markers = useMemo(() => points
    .filter((p) => !hidden.has(p.type) && p.lat != null && p.lng != null)
    .filter((p) => !statut || p.statut === statut)
    .map((p) => ({
      id: p.id,
      lat: p.lat,
      lng: p.lng,
      label: p.label,
      color: COLOR[p.type] || '#64748b',
      detail_path: p.detail_path,
      popupHtml: `<div style="margin-top:4px;color:#475569;font-size:0.8rem">`
        + `${p.type_label}${p.statut_label ? ' · ' + p.statut_label : ''}`
        + (p.date ? ` · ${p.date}` : '')
        + `</div>`,
    })), [points, hidden, statut])

  const openRecord = (m) => { if (m.detail_path) navigate(m.detail_path) }

  return (
    <div className="page">
      <div className="page-header" style={{ flexWrap: 'wrap', gap: '0.75rem' }}>
        <h2>Carte</h2>
        <span style={{ color: '#64748b', fontSize: '0.85rem' }}>
          {counts.total ? `${counts.total} point(s) géolocalisé(s)` : ''}
        </span>
      </div>

      {/* Filtres par type (légende cliquable) + filtre par statut. */}
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.5rem',
        alignItems: 'center', marginBottom: '0.75rem' }}>
        {TYPES.map((t) => {
          const off = hidden.has(t.key)
          const n = counts[t.key] || 0
          return (
            <button key={t.key} type="button" onClick={() => toggleType(t.key)}
              title={off ? 'Afficher' : 'Masquer'}
              style={{
                display: 'inline-flex', alignItems: 'center', gap: 6,
                padding: '3px 10px', borderRadius: 999, cursor: 'pointer',
                border: `1px solid ${t.color}`, fontSize: '0.8rem',
                background: off ? 'transparent' : t.color,
                color: off ? t.color : '#fff',
              }}>
              <span style={{ width: 8, height: 8, borderRadius: 999,
                background: off ? t.color : '#fff' }} />
              {t.label}{n ? ` (${n})` : ''}
            </button>
          )
        })}

        <select
          value={statut}
          onChange={(e) => setStatut(e.target.value)}
          aria-label="Filtrer par statut"
          style={{
            marginLeft: 'auto', padding: '4px 10px', borderRadius: 8,
            border: '1px solid #cbd5e1', fontSize: '0.8rem',
            background: '#fff', color: '#334155',
          }}>
          <option value="">Tous les statuts</option>
          {statutOptions.map((s) => (
            <option key={s.value} value={s.value}>{s.label}</option>
          ))}
        </select>
      </div>

      {err && <p style={{ color: '#dc2626' }}>{err}</p>}
      {loading && <p className="page-loading">Chargement…</p>}

      {!loading && !err && markers.length === 0 && (
        <p style={{ color: '#94a3b8', padding: '1rem 0' }}>
          Aucun enregistrement géolocalisé. Ajoutez les coordonnées GPS sur les
          leads et les chantiers pour les voir ici.
        </p>
      )}

      <MapView markers={markers} onMarkerClick={openRecord} />
    </div>
  )
}
