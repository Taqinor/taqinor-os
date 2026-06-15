import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    react(),
    tailwindcss(),
    // PWA : Taqinor OS devient installable (« Ajouter à l'écran d'accueil »),
    // s'ouvre en plein écran comme une app native, et se met à jour tout seul.
    // SW personnalisé (injectManifest) pour servir une page hors-ligne brandée.
    // On NE met JAMAIS l'API en cache : seul le shell de l'app est précaché.
    VitePWA({
      strategies: 'injectManifest',
      srcDir: 'src',
      filename: 'sw.js',
      registerType: 'autoUpdate', // skipWaiting + clientsClaim dans sw.js
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
})
