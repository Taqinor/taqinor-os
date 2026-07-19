import { useEffect, useState, useCallback, useRef } from 'react'
import { Link } from 'react-router-dom'
import { Bell, Clock3, X } from 'lucide-react'
import adsengineApi from './adsengineApi'

/* ============================================================================
   PUB48 — Centre de notifications persistant de la console (« cloche »).
   ----------------------------------------------------------------------------
   Historique COMPLET (résolues/reportées incluses, ``alerts.history()``) —
   pas un bandeau éphémère qui disparaît au refresh et n'existait que sur le
   Dashboard. Chaque alerte pousse DÉJÀ une notification dans le moteur UNIFIÉ
   de l'ERP côté backend (``apps.adsengine.alerts.notify_alert_recipients`` →
   ``notifications.Notification``, LA MÊME table que la cloche globale du
   header — jamais un second système). Cette cloche CONSOLE offre en plus le
   SNOOZE par alerte (backend ``detail.snoozed_until``, aucune migration) et
   un lien direct vers l'entité (``link``, calculé serveur,
   ``deep_link_for_alert``).

   Lu/non-lu est suivi LOCALEMENT (horodatage du dernier survol de la
   cloche, ``localStorage``) — LIMITE assumée et documentée : ne se
   synchronise pas entre appareils (contrairement à la cloche globale de
   l'ERP, qui elle utilise le moteur ``notify()`` complet avec lu/non-lu
   persisté serveur).
   ========================================================================== */

const SEVERITY_TONES = {
  critical: { bg: '#fee2e2', color: '#991b1b', label: 'Urgent' },
  warning: { bg: '#ffedd5', color: '#9a3412', label: 'Attention' },
  info: { bg: '#e0f2fe', color: '#075985', label: 'Info' },
}
function severityTone(sev) {
  return SEVERITY_TONES[sev] || SEVERITY_TONES.info
}

const LAST_SEEN_KEY = 'ae_alertcenter_last_seen_at'

function readLastSeen() {
  try { return localStorage.getItem(LAST_SEEN_KEY) || '' } catch { return '' }
}
function writeLastSeen(iso) {
  try { localStorage.setItem(LAST_SEEN_KEY, iso) } catch { /* best-effort */ }
}

function defaultSnoozeDate() {
  const d = new Date()
  d.setDate(d.getDate() + 1)
  return d.toISOString().slice(0, 10)
}

export default function AlertCenter() {
  const [open, setOpen] = useState(false)
  const [items, setItems] = useState([])
  const [loading, setLoading] = useState(false)
  const [snoozingId, setSnoozingId] = useState(null)
  const [snoozeDate, setSnoozeDate] = useState(defaultSnoozeDate)
  const [err, setErr] = useState('')
  const [lastSeen, setLastSeen] = useState(readLastSeen)
  const ref = useRef(null)

  const load = useCallback(() => {
    setLoading(true)
    adsengineApi.alerts.history()
      .then(r => setItems(Array.isArray(r.data) ? r.data : (r.data?.results || [])))
      .catch(() => setItems([]))
      .finally(() => setLoading(false))
  }, [])

  // eslint-disable-next-line react-hooks/set-state-in-effect -- chargement au montage
  useEffect(() => { load() }, [load])

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const unreadCount = items.filter(
    a => !lastSeen || (a.created_at && a.created_at > lastSeen)).length

  const toggleOpen = () => {
    const next = !open
    setOpen(next)
    if (next) {
      const now = new Date().toISOString()
      writeLastSeen(now)
      setLastSeen(now)
      load()
    }
  }

  const openSnooze = (a) => {
    setSnoozingId(a.id)
    setSnoozeDate(defaultSnoozeDate())
    setErr('')
  }

  const confirmSnooze = async (id) => {
    setErr('')
    try {
      await adsengineApi.alerts.snooze(id, snoozeDate)
      setSnoozingId(null)
      load()
    } catch {
      setErr('Report impossible.')
    }
  }

  return (
    <div className="ae-alert-center" data-testid="ae-alert-center" ref={ref}
      style={{ position: 'relative' }}>
      <button type="button" className="btn btn-light ae-alert-center-toggle"
        data-testid="ae-alert-center-toggle" onClick={toggleOpen}
        aria-label={`Notifications (${unreadCount})`}
        style={{ display: 'inline-flex', alignItems: 'center', gap: '0.3rem' }}>
        <Bell size={16} aria-hidden="true" />
        {unreadCount > 0 && (
          <span data-testid="ae-alert-center-badge"
            style={{ background: '#dc2626', color: '#fff', borderRadius: 999,
              fontSize: '0.7rem', lineHeight: '1rem', padding: '0 0.35rem', minWidth: 16,
              textAlign: 'center', display: 'inline-block' }}>
            {unreadCount > 99 ? '99+' : unreadCount}
          </span>
        )}
      </button>

      {open && (
        <div className="ae-alert-center-panel" data-testid="ae-alert-center-panel"
          style={{ position: 'absolute', right: 0, top: '100%', zIndex: 20, width: 360,
            maxHeight: 420, overflowY: 'auto', background: '#fff', border: '1px solid #e2e8f0',
            borderRadius: 8, boxShadow: '0 8px 24px rgba(0,0,0,0.12)', padding: '0.5rem' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center',
            padding: '0.3rem 0.4rem' }}>
            <strong>Notifications</strong>
            <button type="button" className="btn btn-light" data-testid="ae-alert-center-close"
              onClick={() => setOpen(false)} aria-label="Fermer">
              <X size={14} aria-hidden="true" />
            </button>
          </div>

          {err && <p data-testid="ae-alert-center-err" style={{ color: '#dc2626', fontSize: '0.8rem', margin: '0.2rem 0.4rem' }}>{err}</p>}

          {loading
            ? <p style={{ padding: '0.5rem' }}>Chargement…</p>
            : items.length === 0
              ? <p data-testid="ae-alert-center-empty" style={{ color: '#64748b', padding: '0.5rem' }}>
                  Aucune alerte.</p>
              : (
                <ul style={{ listStyle: 'none', margin: 0, padding: 0, display: 'grid', gap: '0.4rem' }}>
                  {items.map(a => {
                    const tone = severityTone(a.severity)
                    const snoozed = !!a.snoozed_until
                    return (
                      <li key={a.id} className="ae-alert-center-item" data-testid="ae-alert-center-item"
                        style={{ padding: '0.5rem', borderRadius: 6, background: '#f8fafc' }}>
                        <div style={{ display: 'flex', gap: '0.4rem', alignItems: 'center', flexWrap: 'wrap' }}>
                          <span className="badge" style={{ background: tone.bg, color: tone.color }}>{tone.label}</span>
                          {a.resolved && (
                            <span className="badge" style={{ background: '#dcfce7', color: '#166534' }}>Résolue</span>
                          )}
                          {snoozed && (
                            <span className="badge" data-testid={`ae-alert-center-snoozed-badge-${a.id}`}
                              style={{ background: '#f1f5f9', color: '#475569' }}>
                              Reportée → {a.snoozed_until}
                            </span>
                          )}
                        </div>
                        <p style={{ margin: '0.3rem 0' }}>{a.message}</p>
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center', flexWrap: 'wrap' }}>
                          {a.link && (
                            <Link to={a.link} className="btn btn-light" data-testid={`ae-alert-center-link-${a.id}`}
                              onClick={() => setOpen(false)}>
                              Ouvrir
                            </Link>
                          )}
                          {!a.resolved && !snoozed && (
                            snoozingId === a.id ? (
                              <>
                                <input type="date" value={snoozeDate} className="form-input"
                                  data-testid={`ae-alert-center-snooze-date-${a.id}`}
                                  aria-label="Reporter jusqu'au"
                                  onChange={e => setSnoozeDate(e.target.value)}
                                  style={{ fontSize: '0.8rem' }} />
                                <button type="button" className="btn btn-primary"
                                  data-testid={`ae-alert-center-snooze-confirm-${a.id}`}
                                  onClick={() => confirmSnooze(a.id)}>
                                  Reporter
                                </button>
                              </>
                            ) : (
                              <button type="button" className="btn btn-light"
                                data-testid={`ae-alert-center-snooze-${a.id}`}
                                onClick={() => openSnooze(a)}
                                style={{ display: 'inline-flex', alignItems: 'center', gap: '0.25rem' }}>
                                <Clock3 size={13} aria-hidden="true" /> Reporter
                              </button>
                            )
                          )}
                        </div>
                      </li>
                    )
                  })}
                </ul>
              )}
        </div>
      )}
    </div>
  )
}
