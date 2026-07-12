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
import { useNavigate, useLocation } from 'react-router-dom'
import {
  Bell, Clock, ShieldCheck, Banknote, X, BellRing, Check, Settings,
  CalendarClock, RefreshCw, Inbox, EyeOff,
} from 'lucide-react'
import reportingApi from '../../api/reportingApi'
import notificationsApi from '../../api/notificationsApi'
import { toastInfo, toastWithUndo } from '../../lib/toast'
// VX86 — compteur partagé des approbations en attente (même source que le
// badge nav Sidebar et la carte Dashboard) : rangée « N approbations » en
// tête de la cloche.
import { useApprobationsCount } from '../../hooks/useApprobationsCount'
// VX56 — sondage sensible à la visibilité de l'onglet (patron partagé avec
// `useChatPolling`) : cesse de sonder un onglet caché.
import useVisibilityAwarePolling from '../../hooks/useVisibilityAwarePolling'
// VX217(a) — aperçu sans naviguer (survol desktop / appui long mobile).
import AttentionPeek from '../../features/queue/AttentionPeek'

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

// VX208(a) — regroupe les notifications partageant le même `link` non vide :
// « 5 notifs même facture » ne doit plus faire 5 lignes mais UNE, pliée, avec
// son compteur. Les items sans `link` ne sont JAMAIS fusionnés (pas de fausse
// identité). `feed` est déjà trié du plus récent au plus ancien par le
// backend : la première occurrence rencontrée porte donc le titre le plus
// récent, conservé tel quel. `read` de l'entrée pliée n'est vrai que si
// TOUTES les occurrences sous-jacentes le sont (sinon elle reste « non lue »).
function dedupeByLink(items) {
  const order = []
  const byKey = new Map()
  for (const n of items) {
    const key = n.link ? `link:${n.link}` : `id:${n.id}`
    const existing = byKey.get(key)
    if (existing) {
      existing.count += 1
      existing.ids.push(n.id)
      existing.read = existing.read && n.read
    } else {
      const entry = { ...n, count: 1, ids: [n.id] }
      byKey.set(key, entry)
      order.push(entry)
    }
  }
  return order
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

// VX204 — seuil d'échecs consécutifs de sondage (compteur badge) au-delà
// duquel on affiche un indicateur discret « Mise à jour interrompue ».
const STALL_THRESHOLD = 3

// VX14 — Config DÉCLARATIVE des onglets du panneau (delta mince, vérifié).
// Le panneau groupait DÉJÀ par domaine en sections empilées ; on les range
// désormais dans 2-3 onglets internes avec compteur. Ajouter un domaine =
// une entrée `groups` ici (pas du JSX copié) : chaque groupe déclare son id
// (utilisé pour router son propre rendu existant) + une fonction `count(ctx)`
// qui lit l'état du panneau (feed/data/approbations) pour le compteur total
// de l'onglet — aucune duplication du rendu de groupe lui-même.
const NOTIF_TABS = [
  {
    id: 'activites',
    label: 'Activités',
    groups: ['approbations', 'feed', 'activites_en_retard'],
    // VX208(b) — `feedActionsUnread` (jamais le `feedUnread` brut incluant
    // les digests) : le compteur d'onglet suit la même règle que le badge.
    count: (ctx) =>
      (ctx.showApprobationsRow ? ctx.approbationsTotal : 0) +
      ctx.feedActionsUnread +
      (ctx.data?.activites_en_retard?.length ?? 0),
  },
  {
    id: 'echeances',
    label: 'Échéances',
    groups: ['garanties_expirantes', 'contrats_a_renouveler', 'visites_dues'],
    count: (ctx) =>
      (ctx.data?.garanties_expirantes?.length ?? 0) +
      (ctx.data?.contrats_a_renouveler?.length ?? 0) +
      (ctx.data?.visites_dues?.length ?? 0),
  },
  {
    id: 'financier',
    label: 'Financier',
    groups: ['factures_impayees'],
    count: (ctx) => ctx.data?.factures_impayees?.length ?? 0,
  },
]

export default function NotificationBell() {
  const [data, setData] = useState(null)
  // L11 — distinguer un échec de fetch d'un vrai « rien à signaler ».
  const [derivedError, setDerivedError] = useState(false)
  // L11 — état de chargement (panneau vide → « Chargement… » au 1er fetch).
  const [loaded, setLoaded] = useState(false)
  // N75 — notifications in-app PERSISTÉES (moteur unifié) : feed + compteur.
  const [feed, setFeed] = useState([])
  const [feedUnread, setFeedUnread] = useState(0)
  // VX208(b) — deux compteurs distincts : ACTIONS (badge rouge cloche, un
  // `DIGEST` n'y contribue JAMAIS) vs INFOS (point gris, informationnel).
  const [feedActionsUnread, setFeedActionsUnread] = useState(0)
  const [feedInfosUnread, setFeedInfosUnread] = useState(0)
  const [open, setOpen] = useState(false)
  // VX14 — onglet interne actif du panneau (déclaratif, voir NOTIF_TABS).
  const [activeTab, setActiveTab] = useState(NOTIF_TABS[0].id)
  // VX204 — compteur d'échecs consécutifs du sondage léger (`checkUnread`) :
  // rien ne détectait auparavant une SÉRIE d'échecs (silence total).
  const unreadFailRef = useRef(0)
  const [stalled, setStalled] = useState(false)
  // État de l'autorisation push — lu une fois au montage, jamais demandé ici.
  const [perm, setPerm] = useState(initialPerm)
  // L'invite reste masquée tant que l'utilisateur n'a pas ouvert la cloche.
  const [promptDismissed, setPromptDismissed] = useState(false)
  const ref = useRef(null)
  // Dernier compteur non-lu connu : sert à détecter l'ARRIVÉE d'une nouvelle
  // notification (compteur en hausse) pour déclencher le bip + le toast.
  const prevUnreadRef = useRef(null)
  const navigate = useNavigate()
  // VX82 — chaque changement de route peut poser un NOUVEAU titre de page
  // (`useDocumentTitle` dans la page elle-même) : on réapplique le préfixe
  // juste après pour qu'il survive à la navigation.
  const location = useLocation()
  // VX86 — même hook que le badge nav Sidebar et la carte Dashboard : un seul
  // total cohérent affiché partout.
  const { total: approbationsTotal, loading: approbationsLoading, error: approbationsError } = useApprobationsCount()
  const showApprobationsRow = !approbationsLoading && !approbationsError && approbationsTotal > 0

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
        // VX208(b) — additif : `actions`/`infos` n'existent que depuis ce
        // fix ; `?? 0` couvre un backend pas encore redéployé.
        setFeedActionsUnread(r.data?.actions ?? 0)
        setFeedInfosUnread(r.data?.infos ?? 0)
        // Un succès lève immédiatement l'indicateur de panne prolongée.
        unreadFailRef.current = 0
        setStalled(false)
      })
      .catch(() => {
        unreadFailRef.current += 1
        if (unreadFailRef.current >= STALL_THRESHOLD) setStalled(true)
      })
  }

  const load = () => {
    reportingApi.getNotifications()
      .then((r) => { setData(r.data); setDerivedError(false) })
      .catch(() => { setData(null); setDerivedError(true) })
      .finally(() => setLoaded(true))
    refreshFeed()
  }

  // VX56 — les deux cadences (rafraîchissement complet 3 min, sondage léger
  // 30 s) sont désormais SUSPENDUES quand l'onglet est masqué et rafraîchies
  // immédiatement au retour, via le hook partagé avec `useChatPolling`.
  // `checkUnread` n'est plus appelé À L'INTÉRIEUR de `load` (VX56) : le hook
  // partagé les programme déjà tous les deux au montage — les enchaîner ici
  // aurait doublé chaque appel (mount + tous les ~3 min quand les deux
  // cadences coïncident).
  const { resume: resumePolling } = useVisibilityAwarePolling([
    { fn: load, intervalMs: 3 * 60 * 1000 },
    { fn: checkUnread, intervalMs: 30 * 1000 },
  ])

  // Marque une notification persistée comme lue, puis recharge le compteur.
  // On ne met à jour l'UI QUE si le serveur a confirmé (succès) : un échec ne
  // doit pas faire chuter le compteur faussement — le prochain poll fait foi.
  const markOne = (id) => {
    notificationsApi.markRead(id).then(() => {
      setFeed((prev) => prev.map((n) => (n.id === id ? { ...n, read: true } : n)))
      setFeedUnread((c) => Math.max(0, c - 1))
    }).catch(() => {})
  }

  // VX208(c) — bouton « Marquer non-lu » : `mark_unread` (`views.py:68`,
  // `notificationsApi.js:11`) existait déjà sans le moindre consommateur.
  const markOneUnread = (id) => {
    notificationsApi.markUnread(id).then(() => {
      setFeed((prev) => prev.map((n) => (n.id === id ? { ...n, read: false } : n)))
      setFeedUnread((c) => c + 1)
    }).catch(() => {})
  }

  // VX208(c) — « Tout lu » cesse d'être irréversible : le backend renvoie
  // désormais les `ids` précisément marqués (`mark_all_read`, `views.py`),
  // capturés AVANT la mise à jour — l'« Annuler » restaure PRÉCISÉMENT ces
  // notifications (jamais « toutes les non lues au moment du clic », qui
  // pourrait en inclure de nouvelles arrivées entre-temps) via `mark_unread`
  // un par un (best-effort, chaque échec individuel n'empêche pas les autres).
  const markAll = () => {
    notificationsApi.markAllRead().then((r) => {
      const ids = r.data?.ids ?? []
      const prevFeed = feed
      const prevUnread = feedUnread
      setFeed((prev) => prev.map((n) => ({ ...n, read: true })))
      setFeedUnread(0)
      toastWithUndo({
        message: `${ids.length || 'Tout'} marqué${ids.length > 1 ? 's' : ''} lu.`,
        onUndo: () => {
          setFeed(prevFeed)
          setFeedUnread(prevUnread)
          ids.forEach((id) => { notificationsApi.markUnread(id).catch(() => {}) })
        },
      })
    }).catch(() => {})
  }

  // VX217(b) — « Tout marquer lu » sur un GROUPE plié (VX208 dédoublonnage
  // par `link`, `n.ids` = les ids UNITAIRES sous-jacents). Boucle sur les
  // mêmes mutations `markRead`/`markUnread` déjà existantes — aucune
  // nouvelle mutation serveur — avec un `toastWithUndo` restaurant EXACTEMENT
  // l'état d'avant (mêmes ids, jamais « tout »).
  const markGroupRead = (n) => {
    const idsToMark = (n.ids || [n.id]).filter((id) => {
      const original = feed.find((f) => f.id === id)
      return original && !original.read
    })
    if (idsToMark.length === 0) return
    const prevFeed = feed
    const prevUnread = feedUnread
    setFeed((prev) => prev.map((f) => (
      idsToMark.includes(f.id) ? { ...f, read: true } : f)))
    setFeedUnread((c) => Math.max(0, c - idsToMark.length))
    idsToMark.forEach((id) => { notificationsApi.markRead(id).catch(() => {}) })
    toastWithUndo({
      message: `${idsToMark.length} notification${idsToMark.length > 1 ? 's' : ''} marquée${idsToMark.length > 1 ? 's' : ''} lue${idsToMark.length > 1 ? 's' : ''}.`,
      onUndo: () => {
        setFeed(prevFeed)
        setFeedUnread(prevUnread)
        idsToMark.forEach((id) => { notificationsApi.markUnread(id).catch(() => {}) })
      },
    })
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
  // in-app persistées non lues. VX207 — inclut désormais les approbations en
  // attente (même compteur canonique `attention-summary` que le badge
  // sidebar et l'en-tête « Ma file » via `useApprobationsCount`) : avant ce
  // fix, la cloche pouvait afficher « 0 » pendant que la rangée « N
  // approbations » du panneau ouvert affichait 5 — un badge qui ment.
  // VX208(b) — utilise `feedActionsUnread` (jamais `feedUnread` brut) : un
  // `DIGEST` non lu ne doit JAMAIS gonfler ce badge ACTIONS ; il reste visible
  // séparément (point gris INFOS) sans jamais compter ici.
  const total = derivedTotal + feedActionsUnread + (showApprobationsRow ? approbationsTotal : 0)

  // VX82 — préfixe `(N)` sur le titre d'onglet quand des notifications sont
  // non lues (chrome navigateur vivant). La cloche vit dans le header, monté
  // pour toute la durée de vie du SPA — contrairement à `useDocumentTitle`
  // (page-scoped, restaure l'ancien titre au démontage), on RETIRE puis
  // RÉAPPLIQUE juste le préfixe à chaque changement de `total`, sans jamais
  // toucher au reste du titre — ainsi ça compose sans ordre imposé avec le
  // titre de page posé par `useDocumentTitle` (peu importe lequel des deux
  // effets tourne en dernier après une navigation).
  useEffect(() => {
    const stripped = document.title.replace(/^\(\d+\+?\)\s*/, '')
    document.title = total > 0 ? `(${total > 99 ? '99+' : total}) ${stripped}` : stripped
     
  }, [total, location.pathname])

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
          {stalled && (
            <button
              type="button"
              className="nb-stalled"
              onClick={() => { unreadFailRef.current = 0; setStalled(false); resumePolling() }}
            >
              Mise à jour interrompue — reprendre
            </button>
          )}
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
          ) : feed.length === 0 && (!data || derivedTotal === 0) && !showApprobationsRow ? (
            <div className="nb-empty">Rien à signaler 🎉</div>
          ) : (
            <>
              {/* VX14 — onglets internes déclaratifs (NOTIF_TABS) : remplace les
                  groupes empilés par domaine. Chaque onglet affiche son
                  compteur (somme des groupes qu'il contient). */}
              <div className="nb-tabs" role="tablist" aria-label="Catégories de notifications">
                {NOTIF_TABS.map((tab) => {
                  const n = tab.count({ data, feedActionsUnread, showApprobationsRow, approbationsTotal })
                  return (
                    <button
                      key={tab.id}
                      type="button"
                      role="tab"
                      aria-selected={activeTab === tab.id}
                      className={`nb-tab${activeTab === tab.id ? ' nb-tab-active' : ''}`}
                      onClick={() => setActiveTab(tab.id)}
                    >
                      {tab.label}
                      {n > 0 && <span className="nb-tab-count">{n > 99 ? '99+' : n}</span>}
                    </button>
                  )
                })}
              </div>
              {/* VX86 — rangée « N approbations », EN TÊTE (avant les autres
                  groupes) : l'inbox d'approbations dort sinon dans la section
                  ANALYSE de la sidebar sans jamais apparaître ici. */}
              {activeTab === 'activites' && showApprobationsRow && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Inbox size={13} aria-hidden="true" /> Approbations
                    {/* VX249 — pastille partagée (cloche/Ma file/Dashboard) :
                        pleine = décision qui vous attend personnellement. */}
                    <span className="vx-pastille vx-pastille-mine" aria-hidden="true"
                          title="Vous attend personnellement" />
                  </div>
                  <button
                    type="button"
                    className="nb-item"
                    onClick={() => goto('/approbations')}
                  >
                    <span className="nb-overdue">
                      {approbationsTotal} approbation{approbationsTotal > 1 ? 's' : ''} en attente
                    </span>
                  </button>
                </div>
              )}
              {/* VX208 — DIGEST est toujours une INFO pure (jamais une
                  action, jamais mêlé aux vraies notifications) : replié dans
                  son propre groupe, jamais compté dans le badge ACTIONS. */}
              {activeTab === 'activites' && (() => {
                const digestFeed = feed.filter((n) => n.event_type === 'digest')
                const otherFeed = dedupeByLink(
                  feed.filter((n) => n.event_type !== 'digest'))
                if (otherFeed.length === 0 && digestFeed.length === 0) return null
                return (
                  <div className="nb-group">
                    <div className="nb-group-title">
                      <BellRing size={13} aria-hidden="true" /> Activité récente
                      {feedInfosUnread > 0 && (
                        <span style={{
                          marginLeft: 6, color: 'var(--muted-foreground, #888)',
                          fontWeight: 400,
                        }}>
                          · {feedInfosUnread} info{feedInfosUnread > 1 ? 's' : ''}
                        </span>
                      )}
                    </div>
                    {otherFeed.map((n) => (
                    <AttentionPeek key={`peek-${n.id}`} item={n}
                                   onOpen={(it) => it.link && goto(it.link)}>
                      <button type="button"
                              className={`nb-item${n.read ? '' : ' nb-item-unread'}`}
                              style={n.severity === 'critique'
                                ? { borderLeft: '3px solid var(--destructive, #dc2626)' }
                                : undefined}
                              onClick={() => {
                                if (!n.read) markOne(n.id)
                                if (n.link) goto(n.link)
                              }}>
                        <span>
                          {!n.read && <span className="nb-dot" aria-hidden="true" />}
                          {n.title}
                          {n.count > 1 && (
                            <span style={{
                              marginLeft: 4, color: 'var(--muted-foreground, #888)',
                            }}>
                              ×{n.count}
                            </span>
                          )}
                          {/* VX212(a) — « pourquoi je reçois ça » : raison
                              courte + « Régler » → la ligne de préférence de
                              CET événement (jamais besoin de fouiller la
                              grille des 42 événements). */}
                          {n.reason_label && (
                            <span style={{
                              display: 'block', fontSize: '0.75em',
                              color: 'var(--muted-foreground, #888)',
                            }}>
                              {n.reason_label}
                              {' · '}
                              <span role="button" tabIndex={0}
                                    style={{ textDecoration: 'underline', cursor: 'pointer' }}
                                    onClick={(e) => {
                                      e.stopPropagation()
                                      goto(`/parametres/notifications#${n.event_type}`)
                                    }}
                                    onKeyDown={(e) => {
                                      if (e.key === 'Enter' || e.key === ' ') {
                                        e.stopPropagation()
                                        goto(`/parametres/notifications#${n.event_type}`)
                                      }
                                    }}>
                                Régler
                              </span>
                            </span>
                          )}
                        </span>
                        {!n.read ? (
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
                        ) : (
                          // VX208(c) — bouton « Marquer non-lu » : `mark_unread`
                          // avait zéro consommateur avant ce fix.
                          <span className="nb-item-mark"
                                role="button" tabIndex={0}
                                aria-label="Marquer non-lu"
                                onClick={(e) => { e.stopPropagation(); markOneUnread(n.id) }}
                                onKeyDown={(e) => {
                                  if (e.key === 'Enter' || e.key === ' ') {
                                    e.stopPropagation(); markOneUnread(n.id)
                                  }
                                }}>
                            <EyeOff size={13} aria-hidden="true" />
                          </span>
                        )}
                      </button>
                      {/* VX217(b) — actions de GROUPE : « Tout marquer lu »
                          sur un item plié (VX208 dédoublonnage par `link`) —
                          boucle sur les mutations UNITAIRES existantes,
                          jamais une nouvelle mutation serveur. */}
                      {n.count > 1 && !n.read && (
                        <div className="nb-group-actions">
                          <button type="button" className="nb-link-btn"
                                  onClick={(e) => { e.stopPropagation(); markGroupRead(n) }}>
                            <Check size={12} aria-hidden="true" /> Tout marquer lu ({n.count})
                          </button>
                        </div>
                      )}
                    </AttentionPeek>
                    ))}
                    {digestFeed.length > 0 && (
                      <details>
                        <summary style={{
                          cursor: 'pointer', padding: '4px 8px',
                          color: 'var(--muted-foreground, #888)', fontSize: '0.85em',
                        }}>
                          Récapitulatifs ({digestFeed.length})
                        </summary>
                        {digestFeed.map((n) => (
                          <button key={`digest-${n.id}`} type="button"
                                  className="nb-item"
                                  onClick={() => {
                                    if (!n.read) markOne(n.id)
                                    if (n.link) goto(n.link)
                                  }}>
                            <span>{n.title}</span>
                          </button>
                        ))}
                      </details>
                    )}
                  </div>
                )
              })()}
              {activeTab === 'activites' && data && (data.activites_en_retard?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    {/* VX84 — ce groupe est désormais borné à `assigned_to=
                        request.user` côté serveur (même source que « Ma
                        file ») : « pour moi », par opposition aux garanties/
                        contrats ci-dessous qui restent des alertes société. */}
                    <Clock size={13} aria-hidden="true" /> Activités en retard (pour moi)
                    {/* VX249 — même pastille que ci-dessus : ce groupe précis
                        EST personnel (assigned_to=moi), contrairement aux
                        groupes Garanties/Factures/Contrats/Visites plus bas. */}
                    <span className="vx-pastille vx-pastille-mine" aria-hidden="true"
                          title="Vous concerne personnellement" />
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
              {activeTab === 'echeances' && data && (data.garanties_expirantes?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <ShieldCheck size={13} aria-hidden="true" /> Garanties (≤ 90 j)
                    {/* VX249 — pastille contour : alerte SOCIÉTÉ (pas assignée
                        à un utilisateur), même token que ci-dessus. */}
                    <span className="vx-pastille vx-pastille-company" aria-hidden="true"
                          title="Information société" />
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
              {activeTab === 'financier' && data && (data.factures_impayees?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <Banknote size={13} aria-hidden="true" /> Factures impayées
                    <span className="vx-pastille vx-pastille-company" aria-hidden="true"
                          title="Information société" />
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
              {activeTab === 'echeances' && data && (data.contrats_a_renouveler?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <RefreshCw size={13} aria-hidden="true" /> Contrats à renouveler (≤ 90 j)
                    <span className="vx-pastille vx-pastille-company" aria-hidden="true"
                          title="Information société" />
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
              {activeTab === 'echeances' && data && (data.visites_dues?.length ?? 0) > 0 && (
                <div className="nb-group">
                  <div className="nb-group-title">
                    <CalendarClock size={13} aria-hidden="true" /> Visites dues
                    <span className="vx-pastille vx-pastille-company" aria-hidden="true"
                          title="Information société" />
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
              {/* VX14 — onglet actif sans le moindre élément : message dédié
                  plutôt qu'un panneau vide silencieux. */}
              {NOTIF_TABS.find((t) => t.id === activeTab)?.count(
                { data, feedActionsUnread, showApprobationsRow, approbationsTotal },
              ) === 0 && (
                <div className="nb-empty">Rien à signaler ici</div>
              )}
            </>
          )}
        </div>
      )}
    </div>
  )
}
