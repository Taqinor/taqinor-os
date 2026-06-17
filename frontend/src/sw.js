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
