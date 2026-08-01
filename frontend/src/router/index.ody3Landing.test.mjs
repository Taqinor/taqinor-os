// ODY3 — Vérification structurelle (node --test, sans vitest/jsdom dans ce
// worktree) : « ouvrir l'ERP = voir SES apps ».
//   1. la route `/apps` existe (Menu d'accueil ODY2), lazy + WithLayout ;
//   2. `/` porte enfin une garde (`rootLoader`) : authentifié → atterrissage,
//      ANONYME → Login rendu sur place (jamais une redirection vers /login) ;
//   3. `/dashboard` RESTE une route valide (l'app « Tableau de bord ») ;
//   4. la résolution d'atterrissage est PARTAGÉE avec Login.jsx (une seule
//      implémentation, `lib/apps/landing.js`) ;
//   5. le deep-link/F5 n'est jamais intercepté : aucune autre route ne redirige
//      vers `/apps`.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const landingSrc = readFileSync(
  path.join(__dirname, '..', 'lib', 'apps', 'landing.js'), 'utf8',
)
const loginSrc = readFileSync(path.join(__dirname, '..', 'pages', 'Login.jsx'), 'utf8')
const prefsSrc = readFileSync(
  path.join(__dirname, '..', 'pages', 'preferences', 'prefs.js'), 'utf8',
)

test('la route /apps rend le Menu d’accueil (lazy + WithLayout + authLoader)', () => {
  assert.match(routerSrc, /const HomeMenu = lazy\(\(\)\s*=>\s*import\('\.\.\/pages\/home\/HomeMenu'\)\)/)
  assert.match(
    routerSrc,
    /\{\s*path:\s*'\/apps',\s*loader:\s*authLoader,\s*element:\s*<WithLayout><HomeMenu \/><\/WithLayout>\s*\}/,
  )
})

test('`/` porte la garde rootLoader ; un ANONYME y voit toujours Login', () => {
  assert.match(routerSrc, /\{\s*path:\s*'\/',\s*loader:\s*rootLoader,/)
  // Session absente → `null` (Login rendu ici), JAMAIS buildLoginRedirect.
  assert.match(
    routerSrc,
    /const rootLoader = async \(\) => \{[\s\S]*?if \(!user\) return null/,
  )
})

test('`/dashboard` reste une route valide (l’app « Tableau de bord »)', () => {
  assert.match(
    routerSrc,
    /\{\s*path:\s*'\/dashboard',\s*loader:\s*authLoader,\s*element:\s*<WithLayout><Dashboard \/><\/WithLayout>\s*\}/,
  )
})

test('une SEULE résolution d’atterrissage, partagée entre `/` et Login.jsx', () => {
  assert.match(routerSrc, /import \{ resolveLandingFromAuth \} from '\.\.\/lib\/apps\/landing'/)
  assert.match(loginSrc, /import \{ resolveLandingFromAuth \} from '\.\.\/lib\/apps\/landing'/)
  assert.match(routerSrc, /return redirect\(resolveLandingFromAuth\(store\.getState\(\)\.auth\)\)/)
  // Login.jsx ne rejoue PAS la règle dans son coin.
  assert.doesNotMatch(loginSrc, /resolveLandingPath\(/)
})

test('la règle d’atterrissage : préférence VX46 → dernier module VX11 → mono-app → /apps', () => {
  // Ordre lisible dans prefs.js : les deux règles historiques d'abord, puis
  // l'exception mono-app, puis le repli Menu d'accueil.
  assert.match(prefsSrc, /if \(apps\?\.length === 1 && apps\[0\]\?\.to\) return apps\[0\]\.to/)
  assert.match(prefsSrc, /return '\/apps'/)
  assert.doesNotMatch(prefsSrc, /return '\/dashboard'/)
  // `landing.js` alimente la règle avec la source UNIQUE des apps (ODY1).
  assert.match(landingSrc, /buildInstalledApps\(moduleConfigs, \{/)
})

test('le deep-link/F5 n’est jamais intercepté : seule `/` redirige vers l’atterrissage', () => {
  const redirectionsApps = routerSrc.match(/redirect\('\/apps'\)/g) || []
  assert.equal(redirectionsApps.length, 0)
})
