import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'

// La config Vitest n'embarque ni `vite-plugin-pwa` (fournit
// `virtual:pwa-register/react`) ni le plugin `roofbuilder-ts-transpile`
// (alias `@roofbuilder`/`@roofpro`) de `vite.config.js`. Quand un test tire
// transitivement `features/pwa/PwaPrompts.jsx`, `pages/ventes/ToitureDesign.jsx`
// ou `features/ao/toiture/RepriseCarte.jsx` (AOF82, `@roofpro/captureBoot`),
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
      '@roofpro/captureBoot': stub('./src/test/stubs/roofproCaptureBoot.js'),
    },
  },
  test: {
    environment: 'jsdom',
    globals: false,
    // WOW-CI4 — découpage ÉQUILIBRÉ PAR DURÉE en CI. `--shard=i/n` de Vitest
    // répartit le NOMBRE de fichiers, pas le TRAVAIL : mesuré sur le run
    // 32206663106, trois lanes de 265/265/264 fichiers ont couru 381 s / 266 s /
    // 193 s. `scripts/ci_frontend_shard.py` calcule donc la liste exacte de
    // chaque lane à partir des durées mesurées et la passe ici.
    // Vide ou absent (poste de dev, `npm run test:unit`) : comportement d'origine,
    // la suite complète. On lit une liste EXPLICITE plutôt que des arguments
    // positionnels parce que Vitest traite ces derniers comme des FILTRES par
    // sous-chaîne — un chemin préfixe d'un autre embarquerait des fichiers en trop.
    include: process.env.VITEST_INCLUDE
      ? process.env.VITEST_INCLUDE.split(',').map((s) => s.trim()).filter(Boolean)
      : ['src/**/*.test.jsx'],
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
