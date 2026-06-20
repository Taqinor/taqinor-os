import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
// ── E2E (Playwright) ───────────────────────────────────────────────────────
// Two env-gated hooks let the Playwright suite drive the REAL built app on a
// single origin (so the httpOnly auth cookies behave exactly as in prod behind
// nginx) without dragging in the whole docker stack. Neither hook changes a
// normal `vite build` / `vite preview`:
//   • VITE_E2E=1   → drop the service worker from the build (the PWA shell-cache
//                    only adds flakiness to browser tests; the app logic is
//                    identical with it off).
//   • E2E_PROXY=1  → `vite preview` reverse-proxies /api/django + /static to the
//                    Django backend, mirroring nginx's same-origin routing.
const E2E_BUILD = process.env.VITE_E2E === '1'
const E2E_PROXY = process.env.E2E_PROXY === '1'
const E2E_API_TARGET = process.env.E2E_API_TARGET || 'http://127.0.0.1:8000'

export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // PWA : Taqinor OS devient installable (« Ajouter à l'écran d'accueil »),
    // s'ouvre en plein écran comme une app native, et se met à jour tout seul.
    // SW personnalisé (injectManifest) pour servir une page hors-ligne brandée.
    // On NE met JAMAIS l'API en cache : seul le shell de l'app est précaché.
    VitePWA({
      // E2E builds ship without the service worker (see note above).
      disable: E2E_BUILD,
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      // 'prompt' (et NON 'autoUpdate') : un SW fraîchement installé NE prend
      // PAS la main ni ne recharge la page pendant le tout premier chargement
      // (la course skipWaiting/clientsClaim + auto-reload provoquait des
      // rechargements à froid « il faut rafraîchir plusieurs fois » — C2). La
      // mise à jour se fait via le toast « Nouvelle version — Actualiser »
      // (UpdateToast → updateServiceWorker(true) → message SKIP_WAITING).
      registerType: 'prompt',
      injectRegister: false, // l'enregistrement passe par useRegisterSW (React)
      includeAssets: [
        'favicon.svg', 'favicon.ico', 'favicon-16.png', 'favicon-32.png',
        'apple-touch-icon-180.png', 'offline.html',
        'fonts/**/*',
      ],
      manifest: {
        name: 'Taqinor OS',
        short_name: 'Taqinor',
        description:
          'L’ERP solaire de Taqinor : devis, CRM, stock et facturation.',
        lang: 'fr',
        dir: 'ltr',
        display: 'standalone',
        orientation: 'portrait',
        scope: '/',
        // start_url '/' conserve le comportement actuel : connexion si
        // déconnecté, accueil si connecté (l'app route selon l'auth).
        start_url: '/',
        theme_color: '#0f172a', // navy de marque (cf. src/index.css)
        background_color: '#0f172a',
        icons: [
          { src: '/pwa-192.png', sizes: '192x192', type: 'image/png', purpose: 'any' },
          { src: '/pwa-512.png', sizes: '512x512', type: 'image/png', purpose: 'any' },
          { src: '/pwa-maskable-512.png', sizes: '512x512', type: 'image/png', purpose: 'maskable' },
        ],
      },
      injectManifest: {
        // Shell précaché : JS/CSS/HTML/icônes + polices. Pas l'API.
        globPatterns: ['**/*.{js,css,html,svg,png,ico,woff,woff2}'],
        // Les écrans de démarrage iOS sont chargés par l'OS au lancement (1 seul
        // par appareil), pas via le SW : inutile de les précacher (≈2 Mo évités).
        globIgnores: ['**/splash/**'],
        maximumFileSizeToCacheInBytes: 3 * 1024 * 1024,
      },
    }),
  ],
  server: {
    host: true,
    port: 3000,
    watch: {
      usePolling: true,
      interval: 500,
    },
  },
  // O66 — Budget de bundle + découpage des gros vendors.
  // Les grosses dépendances tierces sont isolées dans leurs propres chunks
  // (mises en cache séparément du code applicatif, qui change plus souvent) et
  // un budget d'alerte raisonnable évite les régressions silencieuses de taille.
  // Les pages restent découpées par route (React.lazy dans le routeur).
  // Les chunks `.js` produits restent précachés par le SW : le
  // `injectManifest.globPatterns` ci-dessus inclut déjà `**/*.js`.
  build: {
    chunkSizeWarningLimit: 900, // ko (gzip non compté) — alerte, pas une erreur
    rollupOptions: {
      output: {
        // Découpe les gros vendors en chunks dédiés (mis en cache séparément du
        // code applicatif). Un module hors de ces groupes suit le découpage par
        // route (React.lazy) — comportement par défaut de Rollup conservé.
        manualChunks(id) {
          if (!id.includes('node_modules')) return undefined
          if (/[\\/]node_modules[\\/]recharts[\\/]/.test(id)) return 'recharts'
          if (/[\\/]node_modules[\\/]pdfjs-dist[\\/]/.test(id)) return 'pdfjs-dist'
          if (/[\\/]node_modules[\\/]@radix-ui[\\/]/.test(id)) return 'radix-ui'
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
            return 'react-vendor'
          }
          return undefined
        },
      },
    },
  },
  // `vite preview` is what the E2E suite serves the built app from. With
  // E2E_PROXY=1 it forwards the same-origin API paths to Django, so the browser
  // sees one origin (localhost) exactly like nginx does in production. Without
  // the flag this block is inert, so a normal `npm run preview` is unchanged.
  preview: {
    proxy: E2E_PROXY
      ? {
          '/api/django': { target: E2E_API_TARGET, changeOrigin: true },
          '/static': { target: E2E_API_TARGET, changeOrigin: true },
        }
      : undefined,
  },
})
