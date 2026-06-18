// I38 — Cloche de notifications in-app (aucun email) + invite d'activation des
// notifications push (web-push VAPID, branché plus tard côté backend).
//
// Agrège, à la volée : activités en retard, garanties expirant sous 90 j,
// factures impayées/en retard. Compte + liste cliquable. Périmètre société
// côté serveur.
//
// PUSH : l'invite d'autorisation apparaît UNIQUEMENT à l'ouverture de la cloche
// (jamais au chargement), avec une justification courte. Tout se dégrade en
// no-op silencieux si `Notification` / `serviceWorker` / la clé VAPID manquent —
// aucune erreur, aucun blocage. Le backend web-push n'existe pas encore : on ne
// fait qu'enregistrer la PERMISSION ; l'abonnement réel sera ajouté ensuite.
import { useEffect, useRef, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { Bell, Clock, ShieldCheck, Banknote, X } from 'lucide-react'
import reportingApi from '../../api/reportingApi'

// Le push n'est tentable que si l'API navigateur ET une clé VAPID publique
// (exposée au build) sont présentes. Sinon : no-op total.
const VAPID_PUBLIC_KEY = import.meta.env?.VITE_VAPID_PUBLIC_KEY || ''

function pushSupported() {
  try {
    return (
      typeof window !== 'undefined' &&
      'Notification' in window &&
      'serviceWorker' in navigator &&
      'PushManager' in window
    )
  } catch {
    return false
  }
}

// État d'autorisation initial — lu UNE fois au montage (jamais demandé).
// 'default' | 'granted' | 'denied' | 'unsupported'.
function initialPerm() {
  if (!pushSupported()) return 'unsupported'
  try { return Notification.permission } catch { return 'unsupported' }
}

export default function NotificationBell() {
  const [data, setData] = useState(null)
  const [open, setOpen] = useState(false)
  // État de l'autorisation push — lu une fois au montage, jamais demandé ici.
  const [perm, setPerm] = useState(initialPerm)
  // L'invite reste masquée tant que l'utilisateur n'a pas ouvert la cloche.
  const [promptDismissed, setPromptDismissed] = useState(false)
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

  // Demande l'autorisation à la DEMANDE de l'utilisateur (clic), jamais avant.
  // Ne lève jamais : tout échec → no-op silencieux.
  const askPush = async () => {
    if (!pushSupported()) { setPerm('unsupported'); return }
    try {
      const res = await Notification.requestPermission()
      setPerm(res)
      // Le backend web-push (abonnement VAPID) n'existe pas encore ; on s'arrête
      // proprement ici. Si une clé VAPID et un service worker sont présents,
      // l'abonnement réel pourra être branché plus tard sans changer cette UI.
    } catch {
      // Permission refusée / API indisponible : on ne casse rien.
      setPerm('unsupported')
    }
  }

  // L'invite ne s'affiche QUE : cloche ouverte, push supporté, permission encore
  // « default » (jamais demandée), clé VAPID présente, et non fermée par l'user.
  const showPrompt =
    open && perm === 'default' && pushSupported() &&
    Boolean(VAPID_PUBLIC_KEY) && !promptDismissed

  return (
    <div className="nb-wrap" ref={ref}>
      <button
        type="button"
        className="nb-btn"
        aria-label={`Notifications (${total})`}
        onClick={() => setOpen((v) => !v)}
      >
        <Bell size={19} aria-hidden="true" />
        {total > 0 && <span className="nb-badge">{total > 99 ? '99+' : total}</span>}
      </button>
      {open && (
        <div className="nb-panel" role="menu">
          <div className="nb-header">Notifications</div>

          {showPrompt && (
            <div className="nb-push-prompt">
              <button type="button" className="nb-push-close"
                      onClick={() => setPromptDismissed(true)}
                      aria-label="Masquer l'invite">
                <X size={13} aria-hidden="true" />
              </button>
              <div className="nb-push-title">Activer les notifications</div>
              <div className="nb-push-text">
                Recevez une alerte pour vos relances, garanties et impayés, même
                quand l'onglet est fermé.
              </div>
              <button type="button" className="nb-push-btn" onClick={askPush}>
                Autoriser
              </button>
            </div>
          )}

          {!data || total === 0 ? (
            <div className="nb-empty">Rien à signaler 🎉</div>
          ) : (
            <>
              {(data.activites_en_retard?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Clock size={13} aria-hidden="true" /> Activités en retard
                  </div>
                  {data.activites_en_retard.map((a) => (
                    <button key={`act-${a.id}`} type="button" className="nb-item"
                            onClick={() => goto(a.lead_id ? `/crm/leads?lead=${a.lead_id}` : '/crm/leads')}>
                      <span>{a.label}</span>
                      {a.date && <span className="nb-item-date">{a.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {(data.garanties_expirantes?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <ShieldCheck size={13} aria-hidden="true" /> Garanties (≤ 90 j)
                  </div>
                  {data.garanties_expirantes.map((e) => (
                    <button key={`gar-${e.id}`} type="button" className="nb-item"
                            onClick={() => goto('/equipements')}>
                      <span>{e.label}</span>
                      {e.date && <span className="nb-item-date">{e.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {(data.factures_impayees?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Banknote size={13} aria-hidden="true" /> Factures impayées
                  </div>
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
