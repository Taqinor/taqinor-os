// Service worker Taqinor OS (injectManifest / vite-plugin-pwa).
// Objectifs :
//   - précacher le SHELL de l'app (chargement instantané, ouverture hors ligne)
//   - se mettre à jour tout seul (skipWaiting + clientsClaim) : pas de hard
//     refresh manuel pour Reda/Meryem
//   - servir une page hors-ligne BRANDÉE en dernier recours
//   - ne JAMAIS mettre l'API (/api/...) en cache (l'app reste connectée)
import { precacheAndRoute, cleanupOutdatedCaches, matchPrecache } from 'workbox-precaching'
import { clientsClaim } from 'workbox-core'
import { NavigationRoute, registerRoute } from 'workbox-routing'

// Mise à jour immédiate : le nouveau SW prend la main sans attendre.
self.skipWaiting()
clientsClaim()
cleanupOutdatedCaches()

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
