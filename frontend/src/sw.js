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
    // Conserve le lien interne pour la navigation au clic.
    data: { link: data.link || '/' },
  }
  event.waitUntil(self.registration.showNotification(title, options))
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
