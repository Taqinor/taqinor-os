/**
 * W357 — Service worker minimal, mise en cache uniquement (AUCUN push, aucune
 * notification). Portée volontairement réduite à deux besoins :
 *
 *  1. Coquille applicative (shell) : les fontes, le CSS/JS hashé Astro
 *     (/_astro/*) et le favicon/manifest, pour un premier rendu hors-ligne
 *     acceptable sur une page déjà visitée.
 *  2. La dernière estimation/devis du visiteur : la page
 *     /proposition/<token> qu'il a ouverte est mise en cache au fil de l'eau
 *     (cache-as-you-go, pas de pré-fetch) afin qu'il puisse la retrouver hors
 *     connexion — marché mobile marocain à couverture inégale.
 *
 * Stratégie :
 *  - Documents HTML (navigations) : réseau d'abord, avec repli cache si hors
 *    ligne. Ceci PRÉSERVE l'intention de `Cache-Control: must-revalidate`
 *    posée par le Worker (worker/cache.mjs, W33) — un déploiement reste
 *    toujours reflété immédiatement dès que le réseau répond ; le cache SW
 *    n'est qu'un filet de secours quand il n'y a pas de réponse réseau du
 *    tout, jamais une source servie en priorité.
 *  - Assets statiques (/_astro/*, /fonts/*, /favicon.svg, /site.webmanifest,
 *    icônes) : cache d'abord (immuables ou peu changeants), avec repli
 *    réseau + mise en cache de la réponse.
 *  - Tout le reste (API, POST, cross-origin, /og/*, /photos/*, /videos/*)
 *    n'est JAMAIS intercepté : laissé filer tel quel au réseau.
 *
 * Aucune donnée fabriquée : rien n'est pré-rempli au install — seules les
 * pages réellement visitées par CE visiteur entrent dans le cache.
 */

const CACHE_VERSION = 'taqinor-v1';
const SHELL_CACHE = `${CACHE_VERSION}-shell`;
const PAGES_CACHE = `${CACHE_VERSION}-pages`;
const KNOWN_CACHES = [SHELL_CACHE, PAGES_CACHE];

// Coquille : petite liste stable, jamais de contenu métier fabriqué ici.
const SHELL_URLS = ['/favicon.svg', '/site.webmanifest', '/apple-touch-icon.png'];

self.addEventListener('install', (event) => {
  event.waitUntil(
    caches
      .open(SHELL_CACHE)
      .then((cache) => cache.addAll(SHELL_URLS))
      .catch(() => {
        /* installation best-effort : une icône manquante ne doit jamais
           bloquer l'activation du service worker */
      }),
  );
  self.skipWaiting();
});

self.addEventListener('activate', (event) => {
  event.waitUntil(
    caches
      .keys()
      .then((names) => Promise.all(names.filter((n) => !KNOWN_CACHES.includes(n)).map((n) => caches.delete(n))))
      .then(() => self.clients.claim()),
  );
});

const isShellAsset = (url) =>
  url.origin === self.location.origin &&
  (url.pathname.startsWith('/_astro/') ||
    url.pathname.startsWith('/fonts/') ||
    SHELL_URLS.includes(url.pathname));

// La dernière estimation du visiteur : uniquement la page de proposition
// tokenisée qu'il a réellement ouverte (jamais préchargée, jamais devinée).
const isVisitorEstimatePage = (url) => url.origin === self.location.origin && url.pathname.startsWith('/proposition/');

self.addEventListener('fetch', (event) => {
  const { request } = event;
  if (request.method !== 'GET') return; // jamais de cache pour POST/API mutants

  const url = new URL(request.url);
  if (url.origin !== self.location.origin) return; // jamais cross-origin (API ERP, tuiles carto…)

  if (isShellAsset(url)) {
    event.respondWith(
      caches.open(SHELL_CACHE).then(async (cache) => {
        const cached = await cache.match(request);
        const network = fetch(request)
          .then((response) => {
            if (response && response.ok) cache.put(request, response.clone());
            return response;
          })
          .catch(() => cached);
        return cached || network;
      }),
    );
    return;
  }

  const isNavigation = request.mode === 'navigate' || (request.headers.get('accept') || '').includes('text/html');
  if (isNavigation) {
    const cacheable = isVisitorEstimatePage(url);
    event.respondWith(
      fetch(request)
        .then((response) => {
          // Réseau d'abord : un déploiement reste immédiatement visible.
          if (cacheable && response && response.ok) {
            caches.open(PAGES_CACHE).then((cache) => cache.put(request, response.clone()));
          }
          return response;
        })
        .catch(() => caches.match(request).then((cached) => cached || Response.error())),
    );
  }
  // Tout le reste (API, /og/*, /photos/*, /videos/*…) : non intercepté.
});
