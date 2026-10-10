import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

export default defineConfig([
  // SOLMVP40 — modules sortis du MVP solaire, rangés hors build/lint/tests
  // (code conservé pour retour possible, cf. frontend/parked/README.md).
  globalIgnores(['dist', 'playwright-report', 'test-results', 'e2e/.auth', 'parked/**']),
  {
    files: ['**/*.{js,jsx}'],
    extends: [
      js.configs.recommended,
      reactHooks.configs.flat.recommended,
      reactRefresh.configs.vite,
    ],
    languageOptions: {
      ecmaVersion: 2020,
      globals: globals.browser,
      parserOptions: {
        ecmaVersion: 'latest',
        ecmaFeatures: { jsx: true },
        sourceType: 'module',
      },
    },
    rules: {
      'no-unused-vars': ['error', { varsIgnorePattern: '^[A-Z_]' }],
    },
  },
  // Node-context config + Playwright specs. The specs' page.evaluate callbacks
  // also reference browser globals, so give them both; drop the React-only
  // fast-refresh rule (these are not components).
  {
    files: ['e2e/**/*.js', 'playwright.config.js', 'vite.config.js'],
    languageOptions: {
      ecmaVersion: 'latest',
      globals: { ...globals.browser, ...globals.node },
      parserOptions: { ecmaVersion: 'latest', sourceType: 'module' },
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  // Bibliothèque de primitifs UI (refonte) : par convention shadcn, ces fichiers
  // ré-exportent des primitives Radix, des variantes `cva` et des helpers à côté
  // des composants. La règle fast-refresh (HMR dev uniquement) n'a pas de sens
  // ici — désactivée pour ce répertoire seulement.
  {
    files: ['src/ui/**/*.{js,jsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  // ODY4 — `src/lib/**` est la couche LOGIQUE (hooks, contextes, helpers purs) :
  // elle n'exporte AUCUN composant (vérifié), donc la règle fast-refresh (HMR de
  // dev uniquement) n'a rien à y protéger. Même exception, même raison, que
  // `src/ui/**` ci-dessus. Un composant n'a pas sa place ici : s'il en apparaît
  // un, il doit aller dans `src/ui/` ou `src/components/`, pas désactiver plus.
  {
    files: ['src/lib/**/*.{js,jsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  // Config Vitest + setup RTL : contexte Node/Vitest (pas l'app navigateur).
  {
    files: ['vitest.config.js', 'src/test/**/*.js'],
    languageOptions: {
      globals: { ...globals.browser, ...globals.node },
    },
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  // Tests de composants/UX (RTL + axe) : ce ne sont pas des composants → la règle
  // fast-refresh ne s'y applique pas.
  {
    files: ['src/**/*.test.{js,jsx}'],
    rules: {
      'react-refresh/only-export-components': 'off',
    },
  },
  // APAR64 — garde de classe (critère C13) : aucun dialogue natif
  // (window.confirm/alert/prompt) dans les écrans Paramètres / Approbations ;
  // utiliser le dialogue maison `ui/confirm`. Périmètre volontairement limité.
  {
    files: [
      'src/pages/parametres/**/*.{js,jsx}',
      'src/features/parametres/**/*.{js,jsx}',
      'src/pages/approbations/**/*.{js,jsx}',
    ],
    rules: {
      'no-alert': 'error',
    },
  },
  // AFAC62 — garde de classe (critère C13) : sur les huit écrans de facturation (J5),
  // un `catch` vide (commentaire seul compris) autour d'un `await` avale l'erreur
  // serveur. Un `catch` sans `await` (lecture localStorage) n'est pas visé.
  {
    files: [
      'src/pages/ventes/PaiementDialog.jsx',
      'src/pages/ventes/FactureList.jsx',
      'src/pages/ventes/FactureForm.jsx',
      'src/pages/ventes/RelancesPage.jsx',
      'src/pages/ventes/AvoirsPage.jsx',
      'src/pages/ventes/RemisesEncaissementPage.jsx',
      'src/pages/ventes/MandatsPaiementPage.jsx',
      'src/pages/ventes/PaiementsPage.jsx',
    ],
    rules: {
      'no-restricted-syntax': [
        'error',
        {
          selector: 'TryStatement:has(AwaitExpression) > CatchClause > BlockStatement[body.length=0]',
          message: 'Erreur serveur avalée : affichez-la (useServerFieldErrors/frenchError)',
        },
      ],
    },
  },
])
