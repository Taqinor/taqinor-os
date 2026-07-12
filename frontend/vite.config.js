import { defineConfig, transformWithOxc } from 'vite'
import { readFile } from 'node:fs/promises'
import { fileURLToPath } from 'node:url'
import { dirname, resolve as resolvePath } from 'node:path'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { VitePWA } from 'vite-plugin-pwa'

// Racine du repo (frontend/.. → taqinor-os). Sert à IMPORTER le builder 3D
// vivant du site public (apps/web/src/scripts/roof-tool-pro11.ts) DANS l'ERP
// sans dupliquer son code : la page ToitureDesign l'importe via l'alias
// `@roofbuilder`. On n'édite JAMAIS la source du builder — on ne fait que la
// résoudre par chemin (Rollup suit ses imports relatifs tout seul).
const __dir = dirname(fileURLToPath(import.meta.url))
const WEB_SRC = resolvePath(__dir, '../apps/web/src')

// Le builder 3D importé vit dans `apps/web/src`, à côté d'un `tsconfig.json` qui
// étend `astro/tsconfigs/strict` (astro n'est PAS une dépendance de l'ERP). Le
// transform TS natif de Vite 8 (oxc/rolldown) découvre PAR FICHIER le tsconfig le
// plus proche et tente de résoudre cet `extends` → la build casse
// (« Tsconfig not found astro/tsconfigs/strict »). On ne peut pas éditer apps/web,
// et la découverte native ignore les overrides de config (`oxc.tsconfig`,
// `oxc.tsconfigRaw`, `rollupOptions.tsconfig`…).
//
// Parade (cf. `roofBuilderTsPlugin` ci-dessous) : un plugin `pre` route les
// fichiers `.ts`/`.tsx` du builder vers un ID VIRTUEL (préfixe `\0rb:`) dont le
// nom ne finit PAS par une extension TS — le transform TS natif (filtre
// `/\.(m?ts|[jt]sx)$/`) ne les voit donc jamais et ne déclenche aucune découverte
// de tsconfig. C'est NOTRE plugin qui les charge et les transpile via
// `transformWithOxc`, avec un nom de fichier synthétique rooté dans `frontend/`
// (aucun tsconfig en remontant). Le reste de l'ERP (JS/JSX) garde le pipeline
// standard, inchangé. La source du builder n'est JAMAIS modifiée — seulement lue.
//
// Motif des fichiers TS du builder (apps/web/src/**.ts|tsx). Tolère les deux
// styles de séparateur (Windows `\` / POSIX `/`) car l'`id` vu par les filtres
// Vite peut varier selon la plateforme.
const WEB_TS_RE = /[\\/]apps[\\/]web[\\/]src[\\/].*\.(m?ts|tsx)(\?.*)?$/

// Préfixe d'ID VIRTUEL pour les modules TS du builder. Le CHEMIN du fichier est
// encodé dans l'id et l'id NE finit PAS par `.ts`/`.tsx` → le transform TS
// natif de Vite (dont le filtre `include` est `/\.(m?ts|[jt]sx)$/`) ne le traite
// PAS, donc ne déclenche jamais la découverte du tsconfig astro. C'est NOTRE
// plugin qui charge + transpile ces fichiers (sans découverte de tsconfig).
//
// VX59 — l'id encode un chemin RELATIF à `WEB_SRC` (jamais le chemin ABSOLU du
// disque) : sans ça, le nom de chunk émis par Rollup dérive de cet id et publie
// la structure du disque local dans un asset (non portable entre
// machines/CI — `manualChunks` ci-dessous re-nomme quand même explicitement ce
// chunk en `roof-tool`, mais gardons l'id lui-même propre en profondeur, au cas
// où un id de secours/sourcemap venait à être dérivé de lui).
const RB_PREFIX = '\0rb:'
const toWebSrcRelative = (abs) => {
  const rel = abs.replace(/\\/g, '/').replace(WEB_SRC.replace(/\\/g, '/') + '/', '')
  return rel
}
const fromWebSrcRelative = (rel) => resolvePath(WEB_SRC, rel)
const encodeRb = (abs) => `${RB_PREFIX}${encodeURIComponent(toWebSrcRelative(abs))}`
const decodeRb = (id) => fromWebSrcRelative(decodeURIComponent(id.slice(RB_PREFIX.length)))

function roofBuilderTsPlugin() {
  return {
    name: 'roofbuilder-ts-transpile',
    enforce: 'pre',
    async resolveId(source, importer) {
      // a) Import d'un fichier TS du builder depuis l'ERP (via alias résolu) ou
      //    depuis un autre module virtuel du builder (imports relatifs internes).
      if (importer && importer.startsWith(RB_PREFIX)) {
        // Résolution d'un import relatif DEPUIS un module virtuel : on calcule le
        // chemin réel relatif au fichier réel encodé, et on le re-virtualise.
        const fromAbs = decodeRb(importer)
        const resolved = await this.resolve(source, fromAbs, { skipSelf: true })
        if (resolved && WEB_TS_RE.test(resolved.id.replace(/\\/g, '/'))) {
          return encodeRb(resolved.id)
        }
        return resolved
      }
      // b) Premier saut depuis l'ERP : si la cible se résout vers un TS du builder.
      const resolved = await this.resolve(source, importer, { skipSelf: true })
      if (resolved && WEB_TS_RE.test(resolved.id.replace(/\\/g, '/'))) {
        return encodeRb(resolved.id)
      }
      return null
    },
    async load(id) {
      if (!id.startsWith(RB_PREFIX)) return null
      const abs = decodeRb(id)
      const code = await readFile(abs, 'utf-8')
      const lang = abs.endsWith('.tsx') ? 'tsx' : 'ts'
      // oxc résout le tsconfig à partir du chemin du fichier transpilé ; on lui
      // passe un nom SYNTHÉTIQUE rooté dans `frontend/` (aucun tsconfig en
      // remontant → aucune découverte, donc jamais l'`extends astro/...` qui
      // casse). La transpilation est purement syntaxique (effacement des types).
      const fakeName = resolvePath(__dir, `.roofbuilder-virtual.${lang}`)
      const res = await transformWithOxc(code, fakeName, { lang })
      return { code: res.code, map: res.map ?? null }
    },
  }
}

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
    roofBuilderTsPlugin(),
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
  // Alias d'IMPORT du builder 3D vendu sur le site public — réutilisé tel quel
  // par la page ERP ToitureDesign. `@roofbuilder` pointe sur l'entrée
  // `initRoofToolPro8` ; `@roofpro`/`@rooflib` restent disponibles en repli si
  // un jour la résolution cross-projet de l'entrée échoue (elle ne devrait pas :
  // Rollup suit les imports relatifs par chemin de fichier). La source du builder
  // n'est JAMAIS éditée — uniquement importée.
  resolve: {
    alias: {
      '@roofbuilder': resolvePath(WEB_SRC, 'scripts/roof-tool-pro11.ts'),
      '@roofpro': resolvePath(WEB_SRC, 'scripts/roofPro11'),
      '@rooflib': resolvePath(WEB_SRC, 'lib'),
    },
  },
  server: {
    host: true,
    port: 3000,
    watch: {
      usePolling: true,
      interval: 500,
    },
    // Le builder vit hors de `frontend/` (dans `apps/web/src`) : on autorise le
    // serveur dev à servir ce sous-arbre. Sans effet sur `vite build` (Rollup
    // n'a pas de garde fs.allow), mais nécessaire pour `vite dev`/`preview`.
    fs: {
      allow: [resolvePath(__dir, '..'), __dir],
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
          // VX59 — Le builder roof-tool est chargé par `roofBuilderTsPlugin`
          // (ci-dessus) sous un id VIRTUEL `\0rb:<chemin-relatif-à-WEB_SRC>`.
          // Sans règle dédiée ici, Rollup dérive le nom de chunk directement de
          // cet id — même un chemin relatif publierait la structure interne du
          // dépôt dans le nom d'asset, et resterait sensible au séparateur de
          // chemin de la plateforme. On regroupe donc TOUJOURS ces modules sous
          // le même nom FIXE `roof-tool`, indépendant de la machine — c'est
          // aussi le nom que `check_bundle_budget.mjs` cherche (VENDOR_CHUNK_
          // BUDGETS_KB['roof-tool']) pour lui donner son budget dédié.
          if (id.startsWith(RB_PREFIX)) return 'roof-tool'
          if (!id.includes('node_modules')) return undefined
          // wave-3 CI fix (frontend-perf) — `recharts`/`pdfjs-dist` used to get a
          // FORCED single named chunk here (like `radix-ui`/`react-vendor` below),
          // but Rolldown's cross-chunk module dedup then attached a real symbol
          // from deep inside that forced chunk to the BOOT entry chunk itself
          // (verified via `--sourcemap`: `index-*.js` statically imported a symbol
          // whose sourcemap resolved INTO `node_modules/recharts`/`pdfjs-dist`,
          // even though no boot-graph source file imports either package or the
          // `ui` barrel) — `<link rel="modulepreload">` on every page, `/login`
          // included (`scripts/check_bundle_budget.mjs` HEAVY_VENDOR_CHUNK_NAMES).
          // Leaving these two names OUT of `manualChunks` lets Rolldown's default
          // per-route code-splitting handle them: verified this removes the boot
          // leak entirely (0 modulepreload violations) while total gzip stays
          // comfortably under budget — a real product/perf trade-off (loses the
          // dedicated always-cached vendor chunk for these two), not a hash-based
          // allowlist. `radix-ui`/`react-vendor` don't hit this — no boot-path
          // code deduplicates against them — so they keep their forced chunk.
          if (/[\\/]node_modules[\\/]@radix-ui[\\/]/.test(id)) return 'radix-ui'
          if (/[\\/]node_modules[\\/](react|react-dom|react-router|react-router-dom|scheduler)[\\/]/.test(id)) {
            return 'react-vendor'
          }
          // VX189(a) — 126 chunks JS < 1 Ko gzip (icônes lucide-react
          // individuelles, chacune son propre chunk par défaut avec l'import
          // nommé `import { X } from 'lucide-react'` utilisé partout dans
          // l'app) sur 345 chunks au total : un seul chunk `icons` partagé,
          // mis en cache une fois pour toute l'app plutôt que fragmenté.
          if (/[\\/]node_modules[\\/]lucide-react[\\/]/.test(id)) return 'icons'
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
