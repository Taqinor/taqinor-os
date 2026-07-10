#!/usr/bin/env node
// ARC43 — Scaffolder d'un module frontend ERP « coquille » complet.
// ----------------------------------------------------------------------------
// `frontend/src/router/moduleRoutes.jsx` glob-importe TOUT fichier
// `features/*/module.config.jsx` : y déposer un fichier suffit à faire
// apparaître le module en nav Sidebar + routes, SANS toucher au routeur (voir
// l'en-tête de moduleRoutes.jsx). Ce script génère à la main :
//   1. `frontend/src/features/<name>/module.config.jsx` (nav + route + roles
//      stub) ;
//   2. `frontend/src/api/<name>Api.js`, un client REST bâti sur la factory
//      partagée `api/resource.js` (ARC44 — jamais de crud() re-déclaré) ;
//   3. `frontend/src/features/<name>/<Pascal>List.jsx`, une page d'exemple sur
//      `ui/module` `ListShell` (le même patron que `features/contrats/
//      ContratsList.jsx`).
// Les 3 fichiers générés sont du JS/JSX conforme à `frontend/eslint.config.js`
// (pas de re-déclaration, imports ordonnés, `react-refresh/only-export-
// components` désactivé où c'est le contrat existant pour module.config.jsx).
//
// Usage :
//   node scripts/scaffold-module.mjs <name> [--label "Libellé Sidebar"] [--icon IconName]
//
//   <name>       kebab-case, devient le slug de route et le préfixe API
//                (ex. "demo-arc43" → /demo-arc43, api/demoArc43Api.js).
//   --label      libellé de section Sidebar (défaut : dérivé du nom, MAJUSCULES).
//   --icon       nom d'icône lucide-react (défaut : "Layers").
//
// Playbook (doc courte) :
//   1. Lancer la commande ci-dessus avec le nom du nouveau module.
//   2. `npm run lint` (frontend/) doit rester vert sans y toucher.
//   3. Adapter la page d'exemple générée (colonnes réelles, filtres) et les
//      chemins de la ressource API au(x) vrai(s) endpoint(s) DRF du module.
//   4. Le module apparaît en nav dès le prochain rendu — aucune autre étape
//      (pas de routeur, pas de Sidebar, pas de routes.meta à modifier).
import { existsSync, mkdirSync, writeFileSync } from 'node:fs'
import path from 'node:path'
import { fileURLToPath } from 'node:url'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const REPO_ROOT = path.resolve(__dirname, '..')
const FRONTEND_SRC = path.join(REPO_ROOT, 'frontend', 'src')

function parseArgs(argv) {
  const [name, ...rest] = argv
  const opts = { label: null, icon: 'Layers' }
  for (let i = 0; i < rest.length; i += 1) {
    if (rest[i] === '--label') opts.label = rest[i + 1]
    if (rest[i] === '--icon') opts.icon = rest[i + 1]
  }
  return { name, ...opts }
}

// kebab-case → PascalCase (ex. "demo-arc43" → "DemoArc43").
function toPascalCase(kebab) {
  return kebab
    .split('-')
    .filter(Boolean)
    .map((seg) => seg.charAt(0).toUpperCase() + seg.slice(1))
    .join('')
}

// kebab-case → camelCase (ex. "demo-arc43" → "demoArc43").
function toCamelCase(kebab) {
  const pascal = toPascalCase(kebab)
  return pascal.charAt(0).toLowerCase() + pascal.slice(1)
}

function moduleConfigTemplate({ name, pascal, label, icon, camel }) {
  return `/* eslint-disable react-refresh/only-export-components --
   Fichier de configuration de module (données + composant lazy), pas un module
   de composants : le fast-refresh ne s'y applique pas (cf. moduleRoutes.jsx). */
import { lazy } from 'react'
import { ${icon} } from 'lucide-react'

/* ============================================================================
   Config du module « ${label} » (généré par scripts/scaffold-module.mjs — ARC43).
   ----------------------------------------------------------------------------
   Collectée par le registre \`router/moduleRoutes.jsx\` via glob (nav Sidebar
   gatée, routes.meta, fil d'Ariane, route lazy) — aucun autre fichier à
   modifier pour que le module apparaisse. Stub de rôles à ajuster ci-dessous
   selon le gating réel du backend (le viewset DRF associé doit porter la
   même permission côté serveur).
   ========================================================================== */

const ${pascal}List = lazy(() => import('./${pascal}List'))

const ROLES = ['responsable', 'admin']

const config = {
  key: '${camel}',
  order: 100,
  nav: {
    label: '${label.toUpperCase()}',
    items: [
      {
        to: '/${name}',
        label: '${label}',
        icon: <${icon} size={17} strokeWidth={1.75} aria-hidden="true" />,
        roles: ROLES,
      },
    ],
  },
  titles: [['/${name}', '${label}']],
  sectionLabels: { ${camel}: '${label}' },
  routes: [
    { path: '/${name}', component: ${pascal}List, roles: ROLES },
  ],
}

export default config
`
}

function apiModuleTemplate({ name, camel, pascal }) {
  return `import api from './axios'
import { makeResourceFactory } from './resource'

/* ============================================================================
   ${pascal} — client API du module « ${name} » (généré par
   scripts/scaffold-module.mjs — ARC43). Miroir fin d'un ViewSet DRF au préfixe
   \`/${name}/\`. Sur la factory partagée ARC44 (\`api/resource.js\`) — jamais de
   crud()/resource() re-déclaré localement. Ajuster le chemin ci-dessous au(x)
   vrai(s) endpoint(s) backend avant usage.
   ========================================================================== */

const resource = makeResourceFactory(api, '/${name}')

const ${camel}Api = {
  items: resource('items'),
}

export default ${camel}Api
`
}

function listPageTemplate({ pascal, camel, label }) {
  return `import { useEffect, useMemo, useState } from 'react'
import ${camel}Api from '../../api/${camel}Api'
import { ListShell } from '../../ui/module'

/* ============================================================================
   Page d'exemple du module « ${label} » (généré par
   scripts/scaffold-module.mjs — ARC43). Même patron que
   \`features/contrats/ContratsList.jsx\` : coquille de liste UX1 (ListShell)
   sur la ressource API générée. Remplacer les colonnes et le chargement par
   les vrais champs du module avant mise en usage.
   ========================================================================== */

export default function ${pascal}List() {
  const [rows, setRows] = useState([])
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)

  const load = () => {
    setLoading(true)
    setError(null)
    ${camel}Api.items
      .list()
      .then((res) => setRows(Array.isArray(res.data) ? res.data : (res.data?.results ?? [])))
      .catch(() => setError('Impossible de charger les données.'))
      .finally(() => setLoading(false))
  }

  useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect -- load-on-mount loading state
    load()
  }, [])

  const columns = useMemo(() => [
    {
      id: 'id',
      header: 'ID',
      width: 100,
      accessor: (r) => r.id,
      cell: (v) => <span className="font-mono text-xs">{v}</span>,
    },
  ], [])

  return (
    <ListShell
      title="${label}"
      breadcrumbs={[{ label: '${label}' }]}
      columns={columns}
      rows={rows}
      loading={loading}
      error={error}
      searchable
      emptyTitle="Aucun élément"
      emptyDescription="Aucun élément à afficher pour l'instant."
    />
  )
}
`
}

function main() {
  const { name, label: labelArg, icon } = parseArgs(process.argv.slice(2))
  if (!name || !/^[a-z][a-z0-9-]*$/.test(name)) {
    process.stderr.write(
      'Usage: node scripts/scaffold-module.mjs <name-kebab-case> [--label "Libellé"] [--icon IconName]\n',
    )
    process.exit(1)
  }

  const pascal = toPascalCase(name)
  const camel = toCamelCase(name)
  const label = labelArg || pascal.replace(/([a-z])([A-Z])/g, '$1 $2')

  const featureDir = path.join(FRONTEND_SRC, 'features', name)
  const moduleConfigPath = path.join(featureDir, 'module.config.jsx')
  const listPagePath = path.join(featureDir, `${pascal}List.jsx`)
  const apiPath = path.join(FRONTEND_SRC, 'api', `${camel}Api.js`)

  if (existsSync(moduleConfigPath) || existsSync(apiPath)) {
    process.stderr.write(`Le module "${name}" existe déjà (fichiers présents) — abandon.\n`)
    process.exit(1)
  }

  mkdirSync(featureDir, { recursive: true })
  writeFileSync(
    moduleConfigPath,
    moduleConfigTemplate({
      name, pascal, label, icon, camel,
    }),
  )
  writeFileSync(listPagePath, listPageTemplate({ pascal, camel, label }))
  writeFileSync(apiPath, apiModuleTemplate({ name, camel, pascal }))

  process.stdout.write(
    [
      `Module "${name}" généré :`,
      `  - ${path.relative(REPO_ROOT, moduleConfigPath)}`,
      `  - ${path.relative(REPO_ROOT, listPagePath)}`,
      `  - ${path.relative(REPO_ROOT, apiPath)}`,
      '',
      "Prochaine étape : ajuster l'endpoint API réel puis `npm run lint` (frontend/).",
      '',
    ].join('\n'),
  )
}

main()
