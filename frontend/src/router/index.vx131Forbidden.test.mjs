// VX131(c) — Vérification structurelle (node --test, sans jsdom/vitest dans ce
// worktree) : un refus de rôle/permission (roleLoader) doit atterrir sur un
// écran 403 DÉDIÉ (ui/Forbidden.jsx) au lieu de rebondir en silence vers
// /dashboard.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const forbiddenSrc = readFileSync(
  path.join(__dirname, '..', 'ui', 'Forbidden.jsx'),
  'utf8',
)

test("index.jsx importe Forbidden en lazy depuis '../ui/Forbidden'", () => {
  assert.match(routerSrc, /const Forbidden = lazy\(\(\)\s*=>\s*import\('\.\.\/ui\/Forbidden'\)\)/)
})

test('roleLoader redirige un refus vers /403, plus vers /dashboard', () => {
  assert.match(routerSrc, /return allowed \? null : redirect\('\/403'\)/)
  assert.doesNotMatch(routerSrc, /return allowed \? null : redirect\('\/dashboard'\)/)
})

test('la route "/403" rend Forbidden (dans WithLayout), gatée par authLoader', () => {
  assert.match(
    routerSrc,
    /\{\s*path:\s*'\/403',\s*loader:\s*authLoader,\s*element:\s*<WithLayout><Forbidden \/><\/WithLayout>\s*\}/,
  )
})

test('ui/Forbidden.jsx affiche le message « Accès refusé » avec le ton warning (EmptyState)', () => {
  assert.match(forbiddenSrc, /Accès refusé/)
  assert.match(forbiddenSrc, /tone="warning"/)
})
