// Cloche de notifications in-app (T5) — composant autonome pour le Header.
// Interroge /crm/notifications/ (calculé à la volée côté serveur) : activités
// en retard, garanties bientôt expirées, factures impayées. Aucun email.
import { useEffect, useRef, useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import crmApi from '../api/crmApi'
import './notificationbell.css'

// Rafraîchissement périodique léger (90 s) tant que l'onglet est ouvert.
const POLL_MS = 90000

export default function NotificationBell() {
  const navigate = useNavigate()
  const [data, setData] = useState({ total: 0, groups: [] })
  const [open, setOpen] = useState(false)
  const ref = useRef(null)

  const load = useCallback(() => {
    crmApi.getNotifications()
      .then((r) => setData(r.data ?? { total: 0, groups: [] }))
      .catch(() => {})
  }, [])

  useEffect(() => {
    load()
    const t = setInterval(load, POLL_MS)
    return () => clearInterval(t)
  }, [load])

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const go = (route) => {
    setOpen(false)
    if (route) navigate(route)
  }

  const total = data.total ?? 0

  return (
    <div className="nb-wrap" ref={ref}>
      <button
        type="button"
        className="nb-trigger"
        aria-label={`Notifications (${total})`}
        onClick={() => setOpen((o) => !o)}
      >
        🔔
        {total > 0 && (
          <span className="nb-badge">{total > 99 ? '99+' : total}</span>
        )}
      </button>

      {open && (
        <div className="nb-panel" role="menu">
          <div className="nb-head">Notifications</div>
          {(!data.groups || data.groups.length === 0) && (
            <div className="nb-empty">Rien à signaler.</div>
          )}
          {(data.groups ?? []).map((g) => (
            <div key={g.type} className="nb-group">
              <div className="nb-group-head">
                <span>{g.label}</span>
                <span className="nb-count">{g.count}</span>
              </div>
              {(g.items ?? []).map((it) => (
                <button
                  key={`${g.type}-${it.id}`}
                  type="button"
                  className="nb-item"
                  onClick={() => go(it.route)}
                >
                  {it.label}
                </button>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}
