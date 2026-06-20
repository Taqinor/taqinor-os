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

  // 1) Clé publique VAPID (vide tant que le serveur n'est pas configuré).
  let publicKey = ''
  try {
    const res = await notificationsApi.getVapidPublicKey()
    publicKey = (res.data && res.data.public_key) || ''
  } catch (error) {
    return { ok: false, reason: 'error', error }
  }
  if (!publicKey) return { ok: false, reason: 'unconfigured' }

  // 2) Permission de notifications (demande native si « default »).
  let permission = Notification.permission
  if (permission === 'default') {
    try { permission = await Notification.requestPermission() } catch { /* ignore */ }
  }
  if (permission !== 'granted') return { ok: false, reason: 'denied' }

  // 3) Abonnement PushManager via le service worker déjà enregistré.
  try {
    const reg = await navigator.serviceWorker.ready
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
