// ODY8 — Vérification structurelle (node --test, sans vitest/jsdom dans ce
// worktree) : une route de module DÉSACTIVÉ n'est plus un renvoi muet vers
// /dashboard mais une porte dédiée.
//
// Le refus a UNE seule implémentation (`moduleLoader`, router/index.jsx) et
// DEUX points d'appel : les routes du registre (router/moduleRoutes.jsx, via
// l'injection `buildModuleRoutes({ ..., moduleLoader })`) et les routes
// déclarées directement dans index.jsx. On vérifie les deux.
//
// Acquis VX78/VX131 NON régressés : le catch-all rend toujours NotFound et le
// refus de rôle va toujours sur /403 — jamais sur cet écran (aucune donnée
// révélée à qui n'a pas le droit).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const moduleRoutesSrc = readFileSync(path.join(__dirname, 'moduleRoutes.jsx'), 'utf8')
const ecranSrc = readFileSync(
  path.join(__dirname, '..', 'pages', 'home', 'AppNotInstalled.jsx'), 'utf8',
)

test('moduleLoader redirige un module OFF vers /app-non-activee, plus vers /dashboard', () => {
  assert.match(
    routerSrc,
    /if \(isModuleDisabled\(disabled, key\)\) \{\s*\n\s*return redirect\(`\/app-non-activee\?app=\$\{encodeURIComponent\(key\)\}`\)/,
  )
  assert.doesNotMatch(
    routerSrc,
    /if \(isModuleDisabled\(disabled, key\)\) return redirect\('\/dashboard'\)/,
  )
})

test('la route /app-non-activee rend l’écran dédié (lazy + WithLayout + authLoader)', () => {
  assert.match(
    routerSrc,
    /const AppNotInstalled = lazy\(\(\)\s*=>\s*import\('\.\.\/pages\/home\/AppNotInstalled'\)\)/,
  )
  assert.match(
    routerSrc,
    /\{\s*path:\s*'\/app-non-activee',\s*loader:\s*authLoader,\s*element:\s*<WithLayout><AppNotInstalled \/><\/WithLayout>\s*\}/,
  )
})

test('point d’appel 1 — les routes du REGISTRE passent par moduleLoader', () => {
  assert.match(
    moduleRoutesSrc,
    /const loader = \(c\.key && moduleLoader\) \? moduleLoader\(c\.key, base\) : base/,
  )
  // Aucune copie locale de la règle de refus dans moduleRoutes.jsx.
  assert.doesNotMatch(moduleRoutesSrc, /redirect\(/)
})

test('point d’appel 2 — index.jsx injecte bien moduleLoader dans buildModuleRoutes', () => {
  assert.match(
    routerSrc,
    /buildModuleRoutes\(\{ WithLayout, authLoader, roleLoader, moduleLoader \}\)/,
  )
})

test('le refus de RÔLE reste distinct : /403, jamais l’écran « app non activée »', () => {
  // Acquis VX131 intact — et l'ordre des gardes (base d'abord) fait que le
  // refus de rôle l'emporte : rien n'est révélé sur l'état du module.
  assert.match(routerSrc, /return allowed \? null : redirect\('\/403'\)/)
  assert.match(routerSrc, /const result = await base\(args\)\s*\n[\s\S]{0,200}?if \(result\) return result/)
})

test('l’écran nomme l’app, propose le Menu d’accueil, et le CTA « Activer » est admin-only', () => {
  assert.match(ecranSrc, /useIsAdmin/)
  assert.match(ecranSrc, /n’est pas activée pour votre société/)
  assert.match(ecranSrc, /estAdmin && \(/)
  assert.match(ecranSrc, /to="\/apps"/)
})
