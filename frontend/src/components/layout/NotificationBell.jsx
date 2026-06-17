// T5 + N75 — cloche de notifications in-app (aucun email). Moteur unifié,
// calculé à la volée côté serveur, borné société : activités en retard,
// garanties expirantes, factures impayées, chantiers à planifier/poser,
// visites de maintenance dues, tickets SAV ouverts, stock bas. Chaque type
// respecte la préférence in-app de l'utilisateur (panneau ⚙). L'envoi sortant
// WhatsApp/email/SMS reste gated (G1/G2/G9).
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import reportingApi from '../../api/reportingApi'
import './notificationbell.css'

// Catégorie → titre + route d'ouverture. L'ordre fixe l'affichage.
const CATEGORIES = [
  { key: 'activites_en_retard', title: '⏰ Activités en retard', route: () => '/crm/leads' },
  { key: 'chantiers_a_planifier', title: '🏗 Chantiers à planifier', route: () => '/chantiers' },
  { key: 'maintenance_due', title: '🔧 Maintenance due', route: () => '/sav/contrats' },
  { key: 'tickets_ouverts', title: '🎫 Tickets SAV ouverts', route: () => '/sav' },
  { key: 'garanties_expirantes', title: '🛡 Garanties (≤ 90 j)', route: () => '/equipements' },
  { key: 'factures_impayees', title: '💸 Factures impayées', route: () => '/ventes/factures' },
  { key: 'stock_bas', title: '📦 Stock bas', route: () => '/stock' },
]

export default function NotificationBell() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  const [showPrefs, setShowPrefs] = useState(false)
  const [prefs, setPrefs] = useState([])
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
      if (ref.current && !ref.current.contains(e.target)) {
        setOpen(false); setShowPrefs(false)
      }
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const openPrefs = () => {
    reportingApi.getNotificationPreferences()
      .then((r) => setPrefs(r.data.preferences ?? []))
      .catch(() => setPrefs([]))
    setShowPrefs(true)
  }

  const togglePref = (eventType, current) => {
    reportingApi.setNotificationPreference(eventType, !current)
      .then((r) => { setPrefs(r.data.preferences ?? []); load() })
      .catch(() => {})
  }

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
          <div className="nb-head">
            <span>Notifications</span>
            <button type="button" className="nb-prefs-btn"
                    aria-label="Préférences de notification"
                    onClick={() => (showPrefs ? setShowPrefs(false) : openPrefs())}>⚙</button>
          </div>
          {showPrefs ? (
            <div className="nb-group">
              <div className="nb-group-title">Afficher dans la cloche</div>
              {prefs.map((p) => (
                <label key={p.event_type} className="nb-pref-row">
                  <input type="checkbox" checked={!!p.in_app}
                         onChange={() => togglePref(p.event_type, p.in_app)} />
                  <span>{p.label}</span>
                </label>
              ))}
            </div>
          ) : !data || total === 0 ? (
            <div className="nb-empty">Rien à signaler 🎉</div>
          ) : (
            CATEGORIES.map((cat) => {
              const items = data[cat.key] ?? []
              if (items.length === 0) return null
              return (
                <div className="nb-group" key={cat.key}>
                  <div className="nb-group-title">{cat.title}</div>
                  {items.map((it) => (
                    <button key={`${cat.key}-${it.id}`} type="button" className="nb-item"
                            onClick={() => goto(
                              cat.key === 'activites_en_retard' && it.lead_id
                                ? `/crm/leads?lead=${it.lead_id}` : cat.route(it))}>
                      <span className={it.overdue ? 'nb-overdue' : undefined}>{it.label}</span>
                      {(it.date || it.sublabel) && (
                        <span className="nb-item-date">{it.date || it.sublabel}</span>
                      )}
                    </button>
                  ))}
                </div>
              )
            })
          )}
        </div>
      )}
    </div>
  )
}
