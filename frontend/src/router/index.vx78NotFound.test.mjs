// VX78 — Vérification structurelle (node --test, sans vitest/jsdom disponibles
// dans ce worktree) : l'écran 404 déjà construit (ui/NotFound.jsx) doit être
// importé et branché sur le catch-all du routeur, au lieu du <Navigate
// to="/dashboard" replace /> silencieux d'avant.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const notFoundSrc = readFileSync(
  path.join(__dirname, '..', 'ui', 'NotFound.jsx'),
  'utf8',
)

test("index.jsx importe NotFound en lazy depuis '../ui/NotFound'", () => {
  assert.match(routerSrc, /const NotFound = lazy\(\(\)\s*=>\s*import\('\.\.\/ui\/NotFound'\)\)/)
})

// NTPRT8 — le catch-all porte désormais `notFoundLoader`, qui ne fait QU'UNE
// chose : renvoyer un compte PORTAIL externe connecté vers son shell (un
// visiteur anonyme voit toujours le 404, cf. index.ntprt8Portail.test.mjs).
// L'invariant VX78 est inchangé : l'élément rendu reste NotFound dans
// WithLayout, jamais une redirection silencieuse vers /dashboard.
test('le catch-all "*" rend NotFound (dans WithLayout), plus de redirection silencieuse', () => {
  assert.match(routerSrc, /\{\s*path:\s*'\*',(?:\s*loader:\s*\w+,)?\s*element:\s*<WithLayout><NotFound \/><\/WithLayout>\s*\}/)
  assert.doesNotMatch(routerSrc, /path:\s*'\*',[^\n]*element:\s*<Navigate to="\/dashboard"/)
})

test('ui/NotFound.jsx affiche bien le message « Page introuvable » attendu par le contrat e2e', () => {
  assert.match(notFoundSrc, /Page introuvable/)
})
