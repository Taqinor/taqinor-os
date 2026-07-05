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
import {
  Bell, Clock, ShieldCheck, Banknote, X, BellRing, Check, Settings,
  CalendarClock, RefreshCw,
} from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import notificationsApi from '../../api/notificationsApi'
import { toastInfo } from '../../lib/toast'

// Bip court (Web Audio) joué à l'arrivée d'une nouvelle notification quand
// l'app est ouverte. Best-effort : échoue silencieusement si l'autoplay audio
// est bloqué (aucun geste utilisateur récent) — aucun asset son embarqué.
function playBeep() {
  try {
    const Ctx = window.AudioContext || window.webkitAudioContext
    if (!Ctx) return
    const ctx = new Ctx()
    const osc = ctx.createOscillator()
    const gain = ctx.createGain()
    osc.connect(gain)
    gain.connect(ctx.destination)
    osc.type = 'sine'
    osc.frequency.value = 880
    gain.gain.setValueAtTime(0.0001, ctx.currentTime)
    gain.gain.exponentialRampToValueAtTime(0.25, ctx.currentTime + 0.02)
    gain.gain.exponentialRampToValueAtTime(0.0001, ctx.currentTime + 0.45)
    osc.start()
    osc.stop(ctx.currentTime + 0.45)
    osc.onended = () => { try { ctx.close() } catch { /* noop */ } }
  } catch { /* best-effort : pas de son si l'autoplay est bloqué */ }
}

// L13 — tri par urgence : le plus en retard d'abord (date la plus ancienne).
// Les éléments sans date passent en fin de liste.
function byUrgency(items) {
  return [...(items || [])].sort((a, b) => {
    if (!a.date) return 1
    if (!b.date) return -1
    return a.date < b.date ? -1 : a.date > b.date ? 1 : 0
  })
}

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
  // L11 — distinguer un échec de fetch d'un vrai « rien à signaler ».
  const [derivedError, setDerivedError] = useState(false)
  // L11 — état de chargement (panneau vide → « Chargement… » au 1er fetch).
  const [loaded, setLoaded] = useState(false)
  // N75 — notifications in-app PERSISTÉES (moteur unifié) : feed + compteur.
  const [feed, setFeed] = useState([])
  const [feedUnread, setFeedUnread] = useState(0)
  const [open, setOpen] = useState(false)
  // État de l'autorisation push — lu une fois au montage, jamais demandé ici.
  const [perm, setPerm] = useState(initialPerm)
  // L'invite reste masquée tant que l'utilisateur n'a pas ouvert la cloche.
  const [promptDismissed, setPromptDismissed] = useState(false)
  const ref = useRef(null)
  // Dernier compteur non-lu connu : sert à détecter l'ARRIVÉE d'une nouvelle
  // notification (compteur en hausse) pour déclencher le bip + le toast.
  const prevUnreadRef = useRef(null)
  const navigate = useNavigate()

  // Recharge la liste in-app persistée (best-effort).
  const refreshFeed = () => {
    notificationsApi.list({ unread: 0 })
      .then((r) => {
        const items = r.data?.results ?? r.data ?? []
        setFeed(Array.isArray(items) ? items.slice(0, 20) : [])
      })
      .catch(() => setFeed([]))
  }

  // Sondage léger du compteur non-lu. Si une nouvelle notification est arrivée
  // (compteur en hausse) ET que ce n'est pas le tout premier chargement, on
  // ALERTE immédiatement : bip sonore + toast + rafraîchit la liste — pour ne
  // pas attendre un rechargement de page. Le push système (bannière OS) reste le
  // canal temps réel quand l'app est fermée ; ceci couvre l'app OUVERTE.
  const checkUnread = () => {
    notificationsApi.unreadCount()
      .then((r) => {
        const n = r.data?.unread ?? 0
        const prev = prevUnreadRef.current
        if (prev !== null && n > prev) {
          playBeep()
          toastInfo('🔔 Nouvelle notification')
          refreshFeed()
        }
        prevUnreadRef.current = n
        setFeedUnread(n)
      })
      .catch(() => {})
  }

  const load = () => {
    reportingApi.getNotifications()
      .then((r) => { setData(r.data); setDerivedError(false) })
      .catch(() => { setData(null); setDerivedError(true) })
      .finally(() => setLoaded(true))
    refreshFeed()
    checkUnread()
  }

  useEffect(() => {
    load()
    // Rafraîchissement complet (alertes dérivées + feed) toutes les 3 min.
    const ivFull = setInterval(load, 3 * 60 * 1000)
    // Sondage léger du compteur toutes les 30 s → alerte sonore + toast quasi
    // temps réel dès qu'une notification arrive, app ouverte.
    const ivPoll = setInterval(checkUnread, 30 * 1000)
    return () => { clearInterval(ivFull); clearInterval(ivPoll) }
    // mount-only: install the two intervals once; `load`/`checkUnread` are
    // re-created each render but read via closure, re-running this on every
    // render would restart both timers continuously.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Marque une notification persistée comme lue, puis recharge le compteur.
  // On ne met à jour l'UI QUE si le serveur a confirmé (succès) : un échec ne
  // doit pas faire chuter le compteur faussement — le prochain poll fait foi.
  const markOne = (id) => {
    notificationsApi.markRead(id).then(() => {
      setFeed((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
      setFeedUnread((c) => Math.max(0, c - 1))
    }).catch(() => {})
  }

  const markAll = () => {
    notificationsApi.markAllRead().then(() => {
      setFeed((prev) => prev.map((n) => ({ ...n, read: true })))
      setFeedUnread(0)
    }).catch(() => {})
  }

  useEffect(() => {
    const onDoc = (e) => {
      if (ref.current && !ref.current.contains(e.target)) setOpen(false)
    }
    document.addEventListener('mousedown', onDoc)
    return () => document.removeEventListener('mousedown', onDoc)
  }, [])

  const derivedTotal = data?.total ?? 0
  // Le compteur de la cloche cumule les alertes dérivées et les notifications
  // in-app persistées non lues.
  const total = derivedTotal + feedUnread
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
          <div className="nb-header">
            Notifications
            <span className="nb-header-actions">
              {feedUnread > 0 && (
                <button type="button" className="nb-link-btn" onClick={markAll}>
                  <Check size={13} aria-hidden="true" /> Tout marquer lu
                </button>
              )}
              <button type="button" className="nb-link-btn"
                      onClick={() => goto('/parametres/notifications')}
                      aria-label="Préférences de notifications">
                <Settings size={13} aria-hidden="true" />
              </button>
            </span>
          </div>

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

          {!loaded ? (
            <div className="nb-empty">Chargement…</div>
          ) : (derivedError && feed.length === 0) ? (
            <div className="nb-empty nb-error" role="alert">
              Notifications indisponibles
            </div>
          ) : feed.length === 0 && (!data || derivedTotal === 0) ? (
            <div className="nb-empty">Rien à signaler 🎉</div>
          ) : (
            <>
              {feed.length > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <BellRing size={13} aria-hidden="true" /> Activité récente
                  </div>
                  {feed.map((n) => (
                    <button key={`notif-${n.id}`} type="button"
                            className={`nb-item${n.read ? '' : ' nb-item-unread'}`}
                            onClick={() => {
                              if (!n.read) markOne(n.id)
                              if (n.link) goto(n.link)
                            }}>
                      <span>
                        {!n.read && <span className="nb-dot" aria-hidden="true" />}
                        {n.title}
                      </span>
                      {!n.read && (
                        <span className="nb-item-mark"
                              role="button" tabIndex={0}
                              aria-label="Marquer comme lu"
                              onClick={(e) => { e.stopPropagation(); markOne(n.id) }}
                              onKeyDown={(e) => {
                                if (e.key === 'Enter' || e.key === ' ') {
                                  e.stopPropagation(); markOne(n.id)
                                }
                              }}>
                          <Check size={13} aria-hidden="true" />
                        </span>
                      )}
                    </button>
                  ))}
                </div>
              )}
              {data && (data.activites_en_retard?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Clock size={13} aria-hidden="true" /> Activités en retard
                  </div>
                  {byUrgency(data.activites_en_retard).map((a) => (
                    <button key={`act-${a.id}`} type="button" className="nb-item"
                            onClick={() => goto(a.lead_id ? `/crm/leads?lead=${a.lead_id}` : '/crm/leads')}>
                      <span className="nb-overdue">{a.label}</span>
                      {a.date && <span className="nb-item-date">{a.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {data && (data.garanties_expirantes?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <ShieldCheck size={13} aria-hidden="true" /> Garanties (≤ 90 j)
                  </div>
                  {byUrgency(data.garanties_expirantes).map((e) => (
                    <button key={`gar-${e.id}`} type="button" className="nb-item"
                            onClick={() => goto('/equipements')}>
                      <span>{e.label}</span>
                      {e.date && <span className="nb-item-date">{e.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {data && (data.factures_impayees?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Banknote size={13} aria-hidden="true" /> Factures impayées
                  </div>
                  {byUrgency(data.factures_impayees).map((f) => (
                    <button key={`fac-${f.id}`} type="button" className="nb-item"
                            onClick={() => goto('/ventes/factures')}>
                      <span className={f.overdue ? 'nb-overdue' : undefined}>{f.label}</span>
                      <span className="nb-item-date">{f.sublabel}</span>
                    </button>
                  ))}
                </div>
              )}
              {data && (data.contrats_a_renouveler?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <RefreshCw size={13} aria-hidden="true" /> Contrats à renouveler (≤ 90 j)
                  </div>
                  {byUrgency(data.contrats_a_renouveler).map((c) => (
                    <button key={`renew-${c.id}`} type="button" className="nb-item"
                            onClick={() => goto('/sav/contrats')}>
                      <span className={c.overdue ? 'nb-overdue' : undefined}>{c.label}</span>
                      {c.date && <span className="nb-item-date">{c.date}</span>}
                    </button>
                  ))}
                </div>
              )}
              {data && (data.visites_dues?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <CalendarClock size={13} aria-hidden="true" /> Visites dues
                  </div>
                  {byUrgency(data.visites_dues).map((v) => (
                    <button key={`visite-${v.id}`} type="button" className="nb-item"
                            onClick={() => goto('/sav/contrats')}>
                      <span className="nb-overdue">{v.label}</span>
                      {v.date && <span className="nb-item-date">{v.date}</span>}
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
