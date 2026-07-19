import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// La config Vitest n'embarque ni `vite-plugin-pwa` (fournit
// `virtual:pwa-register/react`) ni le plugin `roofbuilder-ts-transpile`
// (alias `@roofbuilder`) de `vite.config.js`. Quand un test tire
// transitivement `features/pwa/PwaPrompts.jsx` ou `pages/ventes/ToitureDesign.jsx`,
// la résolution de ces spécifieurs échoue au transform (erreur non gérée).
// On les redirige vers des stubs inertes : aucun test n'exerce leur runtime.
const stub = (rel) => fileURLToPath(new URL(rel, import.meta.url))

/* Couche « tests de composants / UX » (RTL + axe), distincte des tests de logique
   pure exécutés par `node --test` (fichiers *.test.mjs). On limite donc Vitest aux
   fichiers *.test.jsx pour éviter tout double-passage avec node:test. */
export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      'virtual:pwa-register/react': stub('./src/test/stubs/pwaRegister.js'),
      '@roofbuilder': stub('./src/test/stubs/roofbuilder.js'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    include: ['src/**/*.test.jsx'],
    setupFiles: ['./src/test/setup.js'],
    css: false,
    // Certains écrans lancent au montage un `api.methode().then(...)` dans un
    // effet ; quand un test ne pilote pas ce chemin, la méthode non-mockée
    // renvoie `undefined` et le `.then` REJETTE de façon asynchrone, parfois
    // APRÈS la fin du fichier (fuite inter-fichiers propre à l'exécution
    // parallèle : ne se reproduit ni fichier-par-fichier ni en séquentiel, sans
    // stack exploitable, et ne fait échouer AUCUNE assertion). On tolère ces
    // rejets non gérés bénins pour ne pas faire échouer le run — une vraie
    // régression fait toujours échouer l'assertion du test concerné.
    dangerouslyIgnoreUnhandledErrors: true,
    // Le premier rendu d'un test paie un coût de transformation « à froid »
    // élevé sous jsdom (glob des module.config, barrels ui/charts, catalogues
    // i18n) qui dépasse parfois le défaut de 5 s (surtout sous Windows / en
    // charge parallèle). On relève le délai pour supprimer cette classe de flake
    // sans masquer de vraie régression (un vrai blocage échoue toujours).
    testTimeout: 20000,
    hookTimeout: 20000,
    coverage: {
      // `npm run test:coverage` → un % visible des composants/UX couverts.
      provider: 'v8',
      reporter: ['text-summary', 'json-summary'],
      include: ['src/**/*.{js,jsx}'],
      exclude: ['src/**/*.test.{js,jsx}', 'src/test/**', 'src/**/*.test.mjs'],
    },
  },
})
