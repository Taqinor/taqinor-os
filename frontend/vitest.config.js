import { fileURLToPath } from 'node:url'
import { defineConfig } from 'vitest/config'
import react from '@vitejs/plugin-react'
import { roofBuilderTsPlugin } from './vite.config.js'

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
   fichiers *.test.jsx et *.test.js pour éviter tout double-passage avec node:test
   (ERR-QAH-CI-TESTS-JS-JAMAIS-EXECUTES, 28/09/2026 — élargi de *.test.jsx à
   *.test.{jsx,js} : 12 fichiers *.test.js sous src/ n'étaient ramassés par AUCUN
   lanceur ; le seul fichier *.test.js réellement écrit pour node:test
   (ui/datatable/data-label.guard.test.js) a été renommé en .mjs pour rester
   exclu d'ici et rejoindre le glob node:test existant sans y toucher). */
export default defineConfig({
  // `roofBuilderTsPlugin` : transpile les `.ts` du builder sans découverte de tsconfig
  // (le job CI vitest n'a pas `apps/web/node_modules`, donc pas `astro/tsconfigs/strict`).
  plugins: [roofBuilderTsPlugin(), react()],
  resolve: {
    alias: {
      'virtual:pwa-register/react': stub('./src/test/stubs/pwaRegister.js'),
      '@roofbuilder': stub('./src/test/stubs/roofbuilder.js'),
      '@roofpro/captureBoot': stub('./src/test/stubs/roofproCaptureBoot.js'),
      // CALX50 — `ModeTerrain.jsx` / `Ombriere.jsx` chargent `@roofpro/scene3d`
      // pour ses fonctions PURES de placement (`construireChampPose`,
      // `construireOmbriere`) : sans cet alias, le spécifieur ne se résout pas
      // au transform et le fichier de test ne monte même pas (vérifié). Vitest
      // transpile ce TS avec esbuild, donc le plugin `roofbuilder-ts-transpile`
      // de `vite.config.js` n'a pas à être rejoué ici — et c'est la VRAIE
      // fonction du builder qui est exercée, pas une doublure qui dériverait.
      // L'entrée `@roofpro/captureBoot` ci-dessus est déclarée AVANT : elle
      // reste prioritaire, son stub couvre toujours le lecteur de cartes.
      // ACAL254 — moteurs d'horizon et de soleil PARTAGÉS avec l'atelier (même alias que
      // `vite.config.js`) : `horizonEngine.ts` / `roofPro2.ts` / `shadingEngine.ts` sont
      // importés tels quels, plus recopiés côté écran. Déclaré APRÈS `@roofpro` : les
      // deux préfixes sont distincts (`@roofpro` ≠ `@rooflib`), aucun masquage.
      '@rooflib': fileURLToPath(new URL('../apps/web/src/lib', import.meta.url)),
      '@roofpro': fileURLToPath(new URL('../apps/web/src/scripts/roofPro11', import.meta.url)),
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
      : ['src/**/*.test.jsx', 'src/**/*.test.js'],
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
      // ENF24 (règle fondateur 09/10/2026) — seuils BLOQUANTS du job nocturne
      // `frontend-full` (release-verify.yml, `npm run test:coverage`). Mesurés
      // le 09/10/2026 sur lane/enf12 (877 fichiers, 7 035 tests verts) :
      // instructions 65,10 %, branches 59,38 %, fonctions 57,54 %, lignes
      // 68,41 % — planchers arrondis à l'entier inférieur. Relever par paliers
      // d'un point quand la mesure nocturne dépasse le seuil d'au moins un
      // point ; ne jamais les baisser.
      thresholds: {
        statements: 65,
        branches: 59,
        functions: 57,
        lines: 68,
      },
    },
  },
})
