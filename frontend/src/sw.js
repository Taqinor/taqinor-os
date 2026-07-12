// Service worker Taqinor OS (injectManifest / vite-plugin-pwa).
// Objectifs :
//   - précacher le SHELL de l'app (chargement instantané, ouverture hors ligne)
//   - se mettre à jour SUR DEMANDE (toast « Nouvelle version — Actualiser ») :
//     on n'appelle PAS skipWaiting/clientsClaim au démarrage, pour ne JAMAIS
//     prendre la main ni recharger pendant le tout premier chargement (cette
//     course provoquait les rechargements à froid répétés — C2). On ne saute
//     l'attente que lorsque l'app le demande (message SKIP_WAITING).
//   - servir une page hors-ligne BRANDÉE en dernier recours
//   - ne JAMAIS mettre l'API (/api/...) en cache (l'app reste connectée)
import { precacheAndRoute, cleanupOutdatedCaches, matchPrecache } from 'workbox-precaching'
import { NavigationRoute, registerRoute } from 'workbox-routing'
import { StaleWhileRevalidate } from 'workbox-strategies'
import { ExpirationPlugin } from 'workbox-expiration'

cleanupOutdatedCaches()

// Saute l'attente UNIQUEMENT quand l'utilisateur clique « Actualiser » dans le
// toast (vite-plugin-pwa poste ce message via updateServiceWorker(true)). Pas
// de skipWaiting au démarrage → pas de prise de contrôle pendant le 1er
// chargement, donc plus de course de rechargement à froid.
self.addEventListener('message', (event) => {
  if (event.data && event.data.type === 'SKIP_WAITING') {
    self.skipWaiting()
  }
})

// Prend le contrôle des pages déjà ouvertes dès l'activation. REQUIS POUR LE
// PUSH iOS : si on appelle pushManager.subscribe() alors que le service worker
// ne CONTRÔLE pas encore la page (cas typique juste après la 1re installation),
// iOS accepte l'abonnement dans l'UI mais ne livre jamais les push (bug WebKit
// connu). clients.claim() garantit que la page est contrôlée avant l'abonnement.
// Ne ré-ouvre PAS la course de rechargement à froid (C2) : on ne fait TOUJOURS
// PAS de skipWaiting au démarrage, donc sur une mise à jour le nouveau SW reste
// en attente jusqu'à fermeture de l'onglet ; et au tout premier install (aucun
// contrôleur préalable) claim ne déclenche aucun rechargement — le reload n'est
// armé que par le clic « Actualiser » (updateServiceWorker(true)).
self.addEventListener('activate', (event) => {
  event.waitUntil(self.clients.claim())
})

// Précache du shell (liste injectée à la build par vite-plugin-pwa).
precacheAndRoute(self.__WB_MANIFEST || [])

const OFFLINE_URL = 'offline.html'

// Navigations (ouverture d'une page) : réseau d'abord pour toujours afficher la
// dernière version en ligne ; hors ligne, on sert le shell SPA en cache (l'app
// démarre normalement) et, à défaut, la page hors-ligne brandée.
// Les requêtes /api/ ne sont PAS des navigations et restent en réseau pur :
// elles ne sont jamais mises en cache. Le denylist est une ceinture+bretelles.
registerRoute(
  new NavigationRoute(
    async ({ request }) => {
      try {
        return await fetch(request)
      } catch {
        return (
          (await matchPrecache('index.html'))
          || (await matchPrecache(OFFLINE_URL))
          || Response.error()
        )
      }
    },
    { denylist: [/^\/api\//] },
  ),
)

// ── VX179 — cache runtime StaleWhileRevalidate des images/médias dynamiques ──
// Le précache ci-dessus est BUILD-TIME (shell) ; les navigations sont
// network-first. Mais aucune route runtime n'existait pour les images
// GÉNÉRÉES/UPLOADÉES après coup (photos d'installation/GED, images KB) :
// re-téléchargées à chaque visite, et CASSÉES hors-ligne alors que la
// coquille, elle, fonctionne. StaleWhileRevalidate sert le cache
// IMMÉDIATEMENT (rapide, marche hors-ligne) puis rafraîchit en arrière-plan
// (jamais périmé longtemps). `ExpirationPlugin` borne le cache (jamais de
// croissance illimitée). Volontairement SEULEMENT les images — jamais une
// réponse API JSON (règle du fichier : /api/ reste toujours réseau pur, sauf
// ces endpoints binaires précis qui SERVENT une image, pas des données).
const MEDIA_CACHE = 'taqinor-media-v1'
registerRoute(
  ({ request, url }) => (
    request.destination === 'image'
    && url.origin === self.location.origin
    && (
      url.pathname.startsWith('/media/')
      || /^\/api\/django\/kb\/articles\/\d+\/couverture-image\/?$/.test(url.pathname)
      || /^\/api\/django\/ged\/versions\/\d+\/apercu\/?$/.test(url.pathname)
    )
  ),
  new StaleWhileRevalidate({
    cacheName: MEDIA_CACHE,
    plugins: [
      new ExpirationPlugin({ maxEntries: 200, maxAgeSeconds: 30 * 24 * 60 * 60 }),
    ],
  }),
)

// ── N92 — Web push (PWA) ────────────────────────────────────────────────────
// Affiche une notification système à la réception d'un push, et ouvre le lien
// associé au clic. NO-OP tant qu'aucun push n'arrive (le serveur n'envoie rien
// sans clés VAPID configurées). Tout est défensif : un payload malformé ne fait
// jamais planter le service worker.
self.addEventListener('push', (event) => {
  let data = {}
  try {
    data = event.data ? event.data.json() : {}
  } catch {
    // Payload non-JSON : on retombe sur un texte brut comme corps.
    try { data = { body: event.data ? event.data.text() : '' } } catch { data = {} }
  }
  const title = data.title || 'Taqinor OS'
  const options = {
    body: data.body || '',
    icon: '/pwa-192.png',
    badge: '/pwa-192.png',
    // Notification VISIBLE et insistante : la bannière reste affichée jusqu'à
    // ce que l'utilisateur la ferme (au lieu de disparaître seule) et le
    // téléphone vibre. Le SON est joué par l'OS (réglages de notification de
    // l'appareil) — le web ne permet pas d'embarquer un son personnalisé.
    requireInteraction: true,
    vibrate: [200, 100, 200],
    // Regroupe par lien : une nouvelle notification du même enregistrement
    // remplace la précédente, mais re-sonne/re-vibre (renotify).
    tag: data.link || 'taqinor-notif',
    renotify: true,
    // Conserve le lien interne pour la navigation au clic.
    data: { link: data.link || '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
})

// ── N91/F21 — Synchro de la capture terrain hors-ligne ──────────────────────
// L'outbox (file IndexedDB des actions terrain) est vidée par la PAGE (elle a
// le client axios authentifié), pas par le service worker. Quand le navigateur
// déclenche une Background Sync (tag « field-outbox-sync », planifiée par la
// page au moment d'une mise en file hors-ligne), on réveille les onglets
// ouverts pour qu'ils flushent. NO-OP si aucune page n'est ouverte (la page
// flushe de toute façon à son prochain montage / événement « online »).
// Tout est défensif : un échec ne casse jamais le service worker.
function notifyClientsToFlush() {
  return self.clients.matchAll({ type: 'window', includeUncontrolled: true })
    .then((clientList) => {
      for (const client of clientList) {
        try { client.postMessage({ type: 'FIELD_OUTBOX_FLUSH' }) } catch { /* best-effort */ }
      }
    })
    .catch(() => undefined)
}

self.addEventListener('sync', (event) => {
  if (event.tag === 'field-outbox-sync') {
    event.waitUntil(notifyClientsToFlush())
  }
})

self.addEventListener('notificationclick', (event) => {
  event.notification.close()
  const link = (event.notification.data && event.notification.data.link) || '/'
  event.waitUntil(
    self.clients.matchAll({ type: 'window', includeUncontrolled: true })
      .then((clientList) => {
        // Si une fenêtre de l'app est déjà ouverte, on la focalise et l'envoie
        // vers le lien ; sinon on ouvre une nouvelle fenêtre.
        for (const client of clientList) {
          if ('focus' in client) {
            client.focus()
            if ('navigate' in client && link) {
              try { client.navigate(link) } catch { /* best-effort */ }
            }
            return undefined
          }
        }
        if (self.clients.openWindow) return self.clients.openWindow(link)
        return undefined
      }),
  )
})
