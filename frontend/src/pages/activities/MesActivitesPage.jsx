import { useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import recordsApi from '../../api/recordsApi'

const BUCKETS = [
  ['en_retard', 'En retard', '#dc2626'],
  ['aujourdhui', "Aujourd'hui", '#d97706'],
  ['a_venir', 'À venir', '#16a34a'],
]

// Lien profond vers l'enregistrement parent de l'activité.
const targetLink = (a) => {
  if (a.target_model === 'crm.lead') return `/crm/leads?lead=${a.object_id}`
  if (a.target_model === 'crm.client') return '/crm'
  if (a.target_model === 'installations.installation') return '/chantiers'
  if (a.target_model === 'sav.ticket') return '/sav'
  return null
}

export default function MesActivitesPage() {
  const navigate = useNavigate()
  const [data, setData] = useState({ en_retard: [], aujourdhui: [], a_venir: [] })
  const [loading, setLoading] = useState(true)

  const load = () => {
    setLoading(true)
    recordsApi.getMyActivities()
      .then(r => setData(r.data)).catch(() => {}).finally(() => setLoading(false))
  }
  // eslint-disable-next-line react-hooks/set-state-in-effect
  useEffect(() => { load() }, [])

  const markDone = async (a) => {
    try { await recordsApi.markActivityDone(a.id); load() } catch { /* */ }
  }

  const total = data.en_retard.length + data.aujourdhui.length + data.a_venir.length

  return (
    <div className="page">
      <div className="page-header">
        <h2>⏰ Mes activités <span className="count-badge">{total}</span></h2>
      </div>
      {loading && <p className="page-loading">Chargement…</p>}
      {!loading && total === 0 && (
        <p className="gen-hint">Aucune activité planifiée. 🎉</p>
      )}
      {!loading && BUCKETS.map(([key, label, color]) => (
        data[key].length > 0 && (
          <div key={key} style={{ marginBottom: '1.5rem' }}>
            <h3 style={{ fontSize: '0.95rem', color, marginBottom: 8 }}>
              {label} ({data[key].length})
            </h3>
            <table className="data-table">
              <thead>
                <tr>
                  <th>Type</th><th>Résumé</th><th>Échéance</th>
                  <th>Enregistrement</th><th></th>
                </tr>
              </thead>
              <tbody>
                {data[key].map(a => {
                  const link = targetLink(a)
                  return (
                    <tr key={a.id}>
                      <td>{a.activity_type_icone} {a.activity_type_nom}</td>
                      <td>{a.summary || '—'}</td>
                      <td>{a.due_date || '—'}</td>
                      <td>
                        {link ? (
                          <button className="btn btn-sm btn-outline"
                                  onClick={() => navigate(link)}>
                            {a.target_label || 'Ouvrir'}
                          </button>
                        ) : (a.target_label || '—')}
                      </td>
                      <td className="ta-right">
                        <button className="btn btn-sm btn-primary"
                                onClick={() => markDone(a)}>✓ Fait</button>
                      </td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        )
      ))}
    </div>
  )
}
