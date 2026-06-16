// T5 — cloche de notifications in-app (aucun email). Agrège, à la volée :
// activités en retard, garanties expirant sous 90 j, factures impayées/en
// retard. Compte + liste cliquable. Périmètre société côté serveur.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../../api/reportingApi'
import './notificationbell.css'

export default function NotificationBell() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  const ref = useRef(null)
  const navigate = useNavigate()

  const load = () => {
    reportingApi.getNotifications()
      .then((r) => setData(r.data))
      .catch(() => setData(null))
  }

  useEffect(() => {
    load()
    // Rafraîchit périodiquement (5 min) pendant que l'app est ouverte.
    const iv = setInterval(load, 5 * 60 * 1000)
    return () => clearInterval(iv)
  }, [])

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const total = data?.total ?? 0
  const goto = (path) => { navigate(path); setOpen(false) }

  return (
    <div className="nb-wrap" ref={ref}>
      <button
        type="button"
        className="nb-btn"
        aria-label={`Notifications (${total})`}
        onClick={() => setOpen((v) => !v)}
      >
        🔔
        {total > 0 && <span className="nb-badge">{total > 99 ? '99+' : total}</span>}
      </button>
      {open && (
        <div className="nb-panel">
          {!data || total === 0 ? (
            <div className="nb-empty">Rien à signaler 🎉</div>
          ) : (
            <>
              {data.activites_en_retard.length > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">⏰ Activités en retard</div>
                  {data.activites_en_retard.map((a) => (
                    <button key={`act-${a.id}`} type="button" className="nb-item"
                            onClick={() => goto(a.lead_id ? `/crm/leads?lead=${a.lead_id}` : '/crm/leads')}>
                      <span>{a.label}</span>
                      {a.date && <span className="nb-item-date">{a.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {data.garanties_expirantes.length > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">🛡 Garanties (≤ 90 j)</div>
                  {data.garanties_expirantes.map((e) => (
                    <button key={`gar-${e.id}`} type="button" className="nb-item"
                            onClick={() => goto('/equipements')}>
                      <span>{e.label}</span>
                      {e.date && <span className="nb-item-date">{e.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {data.factures_impayees.length > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">💸 Factures impayées</div>
                  {data.factures_impayees.map((f) => (
                    <button key={`fac-${f.id}`} type="button" className="nb-item"
                            onClick={() => goto('/ventes/factures')}>
                      <span className={f.overdue ? 'nb-overdue' : undefined}>{f.label}</span>
                      <span className="nb-item-date">{f.sublabel}</span>
                    </button>
                  ))}
                </div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
