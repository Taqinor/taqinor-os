// VX64 — Vérification structurelle (node --test, sans vitest/jsdom disponibles
// dans ce worktree) : chaque route NUE (sans WithLayout) du routeur doit
// envelopper son élément dans <RouteErrorBoundary>, pour qu'un throw de rendu
// affiche l'écran FR de récupération plutôt qu'une page blanche — vu par des
// clients externes sur les flux publics tokenisés (signature, portail, kiosque…).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')

// Isole le bloc `createBrowserRouter([...])` (routes déclarées directement dans
// ce fichier ; les routes de module viennent de buildModuleRoutes, hors scope).
const routerBlockMatch = routerSrc.match(/createBrowserRouter\(\[([\s\S]*?)\n\]\)/)
assert.ok(routerBlockMatch, 'le bloc createBrowserRouter([...]) doit être trouvable dans index.jsx')
const routerBlock = routerBlockMatch[1]

// Découpe en lignes de déclaration de route (`{ path: '...', ... }`) : on ne
// regarde que les objets qui contiennent une clé `path`.
const routeLines = routerBlock
  .split('\n')
  .filter((line) => /\{\s*path:/.test(line))

// Routes historiquement SANS layout ERP (WithLayout) — celles visées par VX64.
const nakedRoutePaths = [
  '/',
  '/landing',
  '/login',
  '/ui',
  '/rdv/:token',
  '/portail-contrats/:token',
  '/ged/signature/:token',
  '/ged/signataire/:token',
  '/ged/depot/:token',
  '/kiosque',
  '/e/:token',
  '/suivi/:token',
  '/dashboards-tv',
  '/kb/public/:token',
]

test('chaque route nue déclarée est bien enveloppée dans <RouteErrorBoundary>', () => {
  const found = new Set()
  for (const line of routeLines) {
    const pathMatch = line.match(/path:\s*'([^']+)'/)
    if (!pathMatch) continue
    const routePath = pathMatch[1]
    if (!nakedRoutePaths.includes(routePath)) continue
    found.add(routePath)
    assert.match(
      line,
      /<RouteErrorBoundary>/,
      `la route "${routePath}" doit ouvrir <RouteErrorBoundary> autour de son élément`,
    )
    assert.match(
      line,
      /<\/RouteErrorBoundary>\s*\},?\s*$/,
      `la route "${routePath}" doit fermer </RouteErrorBoundary> à la fin de sa déclaration`,
    )
  }
  // Garantit qu'on a bien vérifié TOUTES les routes nues attendues (pas de faux
  // positif si une route a été renommée/déplacée sans mettre à jour ce test).
  for (const expected of nakedRoutePaths) {
    assert.ok(found.has(expected), `route nue attendue introuvable dans le routeur : "${expected}"`)
  }
})

// VX78 — Le catch-all rend désormais l'écran 404 (ui/NotFound.jsx) au lieu de
// rediriger en silence vers /dashboard (un favori/lien périmé doit s'expliquer).
test('le catch-all "*" rend la page 404 (NotFound) au lieu de rediriger silencieusement', () => {
  const catchAllLine = routeLines.find((line) => /path:\s*'\*'/.test(line))
  assert.ok(catchAllLine, 'la route catch-all "*" doit exister')
  assert.match(catchAllLine, /<WithLayout><NotFound \/><\/WithLayout>/, 'le catch-all doit rendre NotFound (dans WithLayout)')
  assert.doesNotMatch(catchAllLine, /<Navigate\s/, 'le catch-all ne doit plus rediriger silencieusement vers /dashboard')
})
