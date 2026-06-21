/* N92 — Helper d'opt-in Web Push (PWA), par appareil.
 *
 * Flux : récupère la clé publique VAPID du backend → demande la permission de
 * notifications → s'abonne via PushManager → poste l'abonnement à l'API. Tout
 * est défensif : si le navigateur ne supporte pas le push, ou si aucune clé
 * VAPID n'est configurée côté serveur (chaîne vide), on renvoie un résultat
 * « non disponible » plutôt que de lever — le push reste alors un NO-OP. */
import notificationsApi from '../../api/notificationsApi'

// True si le navigateur expose le service worker + l'API Push + les notifications.
export function pushSupported() {
  return (
    typeof window !== 'undefined'
    && 'serviceWorker' in navigator
    && 'PushManager' in window
    && 'Notification' in window
  )
}

// Attend que le service worker CONTRÔLE réellement la page courante (pas
// seulement qu'il soit « ready »/actif). Indispensable sur iOS : un abonnement
// push créé alors que la page n'est pas contrôlée est accepté dans l'UI mais
// jamais livré (bug WebKit). Le SW prend le contrôle via clients.claim() à son
// activation ; on attend ici l'évènement `controllerchange` correspondant, avec
// un délai de garde pour ne jamais bloquer indéfiniment.
function waitForController(timeoutMs = 3000) {
  return new Promise((resolve) => {
    if (navigator.serviceWorker.controller) { resolve(true); return }
    let done = false
    const finish = (ok) => {
      if (done) return
      done = true
      navigator.serviceWorker.removeEventListener('controllerchange', onChange)
      resolve(ok)
    }
    const onChange = () => finish(Boolean(navigator.serviceWorker.controller))
    navigator.serviceWorker.addEventListener('controllerchange', onChange)
    // Garde-fou : on tente l'abonnement même si le contrôle n'arrive pas.
    setTimeout(() => finish(Boolean(navigator.serviceWorker.controller)), timeoutMs)
  })
}

// Convertit une clé VAPID base64url (chaîne) en Uint8Array attendu par
// l'option applicationServerKey de PushManager.subscribe().
function urlBase64ToUint8Array(base64String) {
  const padding = '='.repeat((4 - (base64String.length % 4)) % 4)
  const base64 = (base64String + padding).replace(/-/g, '+').replace(/_/g, '/')
  const raw = window.atob(base64)
  const output = new Uint8Array(raw.length)
  for (let i = 0; i < raw.length; i += 1) output[i] = raw.charCodeAt(i)
  return output
}

/* S'abonne au push sur CET appareil. Renvoie un objet de statut :
 *   { ok: true }                          → abonné et enregistré côté serveur
 *   { ok: false, reason: 'unsupported' }  → navigateur sans support push
 *   { ok: false, reason: 'unconfigured' } → pas de clé VAPID côté serveur
 *   { ok: false, reason: 'denied' }       → permission refusée par l'utilisateur
 *   { ok: false, reason: 'error', error } → autre échec (réseau, abonnement…) */
export async function subscribeToPush() {
  if (!pushSupported()) return { ok: false, reason: 'unsupported' }

  // 1) Permission EN PREMIER, de façon synchrone dans le geste utilisateur.
  //    iOS/Safari EXIGE que Notification.requestPermission() soit appelé
  //    directement dans le gestionnaire de clic : tout `await` AVANT (ex. un
  //    fetch réseau) fait perdre le contexte de geste et iOS IGNORE alors
  //    silencieusement la demande → permission jamais accordée, aucun
  //    abonnement, aucune notif (alors que Chrome/Windows, plus laxiste, marche).
  //    On demande donc la permission avant tout appel asynchrone.
  let permission = Notification.permission
  if (permission === 'default') {
    try { permission = await Notification.requestPermission() } catch { /* ignore */ }
  }
  if (permission !== 'granted') return { ok: false, reason: 'denied' }

  // 2) Clé publique VAPID (vide tant que le serveur n'est pas configuré).
  let publicKey = ''
  try {
    const res = await notificationsApi.getVapidPublicKey()
    publicKey = (res.data && res.data.public_key) || ''
  } catch (error) {
    return { ok: false, reason: 'error', error }
  }
  if (!publicKey) return { ok: false, reason: 'unconfigured' }

  // 3) Abonnement PushManager via le service worker déjà enregistré.
  try {
    const reg = await navigator.serviceWorker.ready
    // iOS : s'assurer que le SW CONTRÔLE la page avant de s'abonner, sinon le
    // push n'est jamais livré (bug WebKit). Best-effort, borné dans le temps.
    await waitForController()
    let subscription = await reg.pushManager.getSubscription()
    if (!subscription) {
      subscription = await reg.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(publicKey),
      })
    }
    // 4) Enregistre l'abonnement côté serveur (company + user forcés serveur).
    await notificationsApi.pushSubscribe(subscription.toJSON())
    return { ok: true }
  } catch (error) {
    return { ok: false, reason: 'error', error }
  }
}

/* Désabonne CET appareil : retire l'abonnement local puis informe le serveur. */
export async function unsubscribeFromPush() {
  if (!pushSupported()) return { ok: false, reason: 'unsupported' }
  try {
    const reg = await navigator.serviceWorker.ready
    const subscription = await reg.pushManager.getSubscription()
    if (subscription) {
      const endpoint = subscription.endpoint
      try { await subscription.unsubscribe() } catch { /* best-effort */ }
      try { await notificationsApi.pushUnsubscribe(endpoint) } catch { /* best-effort */ }
    }
    return { ok: true }
  } catch (error) {
    return { ok: false, reason: 'error', error }
  }
}
