import js from '@eslint/js'
import globals from 'globals'
import reactHooks from 'eslint-plugin-react-hooks'
import reactRefresh from 'eslint-plugin-react-refresh'
import { defineConfig, globalIgnores } from 'eslint/config'

// SOL6 — verticaux PARQUÉS hors de l'édition solaire. Source unique partagée
// avec `vite.config.js`, `vitest.config.js` et `scripts/check_dist_edition.mjs`.
import { ARBRES, EDITION_SOLAR, verticauxParques } from './src/lib/editions.js'

const VERTICAUX_PARQUES = verticauxParques(EDITION_SOLAR)

/* Motifs d'import interdits : tout chemin qui atteint `features/<vertical>`,
   `pages/<vertical>` ou `components/<vertical>` d'un vertical parqué. Ces
   arbres sortent ENSEMBLE du build solaire — un import venu d'ailleurs les y
   ferait rentrer par la bande et casserait la garde `check_dist_edition`. */
const MOTIFS_VERTICAUX_PARQUES = VERTICAUX_PARQUES.flatMap((vertical) =>
  ARBRES.flatMap((arbre) => [
    `**/${arbre}/${vertical}`,
    `**/${arbre}/${vertical}/**`,
  ]),
)

/* `no-restricted-imports` ne voit QUE les imports statiques : un
   `import('../features/mrp/…')` (tout le registre de modules fonctionne comme
   ça, via `lazy()`) passerait à travers. On double donc la frontière par un
   sélecteur sur l'expression d'import dynamique — vérifié empiriquement, la
   règle `patterns` seule ne le signale pas. */
const SELECTEUR_IMPORT_DYNAMIQUE_PARQUE =
  `ImportExpression > Literal[value=/(^|\\/)(${ARBRES.join('|')})`
  + `\\/(${VERTICAUX_PARQUES.join('|')})(\\/|$)/]`

const MESSAGE_FRONTIERE =
  'SOL6 — vertical PARQUÉ hors de l\'édition solaire : ne l\'importez pas depuis '
  + 'une surface gardée. Passez par le registre de modules '
  + '(features/<x>/module.config.jsx, chargé par un glob conditionnel) ou, si la '
  + 'surface doit vraiment exister en édition complète, mettez l\'import sous une '
  + 'condition LITTÉRALE build-time (__EDITION_A_<X>__) avec un eslint-disable justifié.'

export default defineConfig([
  globalIgnores(['dist', 'playwright-report', 'test-results', 'e2e/.auth']),
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
  // SOL6 — FRONTIÈRE D'ÉDITION. Aucune surface GARDÉE n'importe un vertical
  // PARQUÉ : sinon Rollup le rattache au graphe et il revient dans le dist
  // solaire malgré le glob conditionnel (la garde `check_dist_edition.mjs`
  // échouerait alors en CI, bien plus tard et bien plus cher qu'ici).
  // `ignores` : les verticaux parqués s'importent librement ENTRE EUX et à
  // l'intérieur de leur propre arbre (ils sortent du build ensemble). Les
  // fichiers de test sont exemptés (ils vérifient justement ces modules).
  {
    files: ['src/**/*.{js,jsx}'],
    ignores: [
      ...VERTICAUX_PARQUES.flatMap((vertical) =>
        ARBRES.map((arbre) => `src/${arbre}/${vertical}/**`)),
      'src/**/*.test.{js,jsx}',
      'src/**/*.test.mjs',
    ],
    rules: {
      'no-restricted-imports': ['error', {
        patterns: [{
          group: MOTIFS_VERTICAUX_PARQUES,
          message: MESSAGE_FRONTIERE,
        }],
      }],
      'no-restricted-syntax': ['error', {
        selector: SELECTEUR_IMPORT_DYNAMIQUE_PARQUE,
        message: MESSAGE_FRONTIERE,
      }],
    },
  },
  // SOL6 — constantes d'édition injectées par `define` (vite/vitest) : ce sont
  // des littéraux de compilation, pas des variables d'exécution.
  {
    files: ['src/**/*.{js,jsx}'],
    languageOptions: {
      globals: {
        __TAQINOR_EDITION__: 'readonly',
        __EDITION_SOLAIRE__: 'readonly',
        __EDITION_A_MRP__: 'readonly',
      },
    },
  },
])
