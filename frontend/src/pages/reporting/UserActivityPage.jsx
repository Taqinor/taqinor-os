import { useEffect, useMemo, useState } from 'react'
import reportingApi from '../../api/reportingApi'

// N70 — Vue activité & accès par utilisateur. Agrège les pistes d'audit/
// activité existantes (chatter CRM / installations / SAV, ProduitAuditLog) +
// SettingsAuditLog en un flux unique scopé société, filtrable par utilisateur
// et par source. Lecture seule.
const SOURCE_LABELS = {
  crm: 'CRM (leads)',
  installations: 'Chantiers',
  sav: 'SAV',
  stock: 'Stock',
  parametres: 'Paramètres',
}

export default function UserActivityPage() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [userId, setUserId] = useState('')
  const [source, setSource] = useState('')

  useEffect(() => {
    let alive = true
    const run = async () => {
      await Promise.resolve()
      if (!alive) return
      setLoading(true)
      try {
        const params = {}
        if (userId) params.user = userId
        if (source) params.source = source
        const r = await reportingApi.getUserActivity(params)
        if (alive) setData(r.data)
      } catch { /* ignore */ }
      if (alive) setLoading(false)
    }
    run()
    return () => { alive = false }
  }, [userId, source])

  // Liste des utilisateurs déduite des évènements (pour le filtre).
  const users = useMemo(() => {
    const seen = new Map()
    for (const e of data?.events ?? []) {
      if (e.user_id != null && !seen.has(e.user_id)) {
        seen.set(e.user_id, e.user)
      }
    }
    return [...seen.entries()].map(([id, nom]) => ({ id, nom }))
  }, [data])

  return (
    <div className="page" style={{ maxWidth: 1100 }}>
      <div className="page-header">
        <h2>Activité par utilisateur</h2>
      </div>

      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: '1rem' }}>
        <select className="input input-sm" value={userId} onChange={e => setUserId(e.target.value)}>
          <option value="">Tous les utilisateurs</option>
          {users.map(u => <option key={u.id} value={u.id}>{u.nom}</option>)}
        </select>
        <select className="input input-sm" value={source} onChange={e => setSource(e.target.value)}>
          <option value="">Toutes les sources</option>
          {Object.entries(SOURCE_LABELS).map(([k, v]) => (
            <option key={k} value={k}>{v}</option>
          ))}
        </select>
      </div>

      {loading || !data ? <p className="page-loading">Chargement…</p> : (
        <div style={{ background: '#fff', borderRadius: 14, padding: '1.1rem 1.3rem', boxShadow: '0 1px 4px rgba(0,0,0,0.07)' }}>
          {data.events.length === 0 ? (
            <p style={empty}>Aucune activité.</p>
          ) : (
            <table className="data-table">
              <thead>
                <tr>
                  <th>Date</th><th>Utilisateur</th><th>Source</th>
                  <th>Cible</th><th>Détail</th>
                </tr>
              </thead>
              <tbody>
                {data.events.map((e, i) => (
                  <tr key={i}>
                    <td>{e.timestamp ? new Date(e.timestamp).toLocaleString('fr-MA') : '—'}</td>
                    <td>{e.user}</td>
                    <td>{SOURCE_LABELS[e.source] || e.source}</td>
                    <td>{e.cible}</td>
                    <td>{e.detail}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      )}
    </div>
  )
}

const empty = { textAlign: 'center', color: '#94a3b8', padding: '1.5rem' }
