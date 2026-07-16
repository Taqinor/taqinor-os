// VX65 — Vérification structurelle (node --test, sans vitest/jsdom disponibles
// dans ce worktree) : le lien profond doit survivre à une reconnexion. On
// vérifie que `authLoader`/`roleLoader` capturent `?next=` depuis le `Request`
// du loader (au lieu de rediriger en dur vers /login) et que Login.jsx suit
// `next` uniquement s'il s'agit d'un chemin interne sûr (garde anti-open-redirect).
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const loginSrc = readFileSync(
  path.join(__dirname, '..', 'pages', 'Login.jsx'),
  'utf8',
)

test('authLoader capture le Request et construit une redirection /login?next=... via buildLoginRedirect', () => {
  assert.match(routerSrc, /const authLoader = async \(\{\s*request\s*\}\)\s*=>/)
  assert.match(routerSrc, /return ok \? null : buildLoginRedirect\(request\)/)
  assert.match(routerSrc, /redirect\(`\/login\?next=\$\{encodeURIComponent\(next\)\}`\)/)
})

test('roleLoader capture aussi le Request pour rediriger via buildLoginRedirect', () => {
  assert.match(
    routerSrc,
    /const roleLoader = \(roles, perm\) => async \(\{\s*request\s*\}\)\s*=>/,
  )
  assert.match(routerSrc, /if \(!ok\) return buildLoginRedirect\(request\)/)
})

test("Login.jsx lit '?next=' via useSearchParams et le suit seulement s'il est sûr", () => {
  assert.match(loginSrc, /useSearchParams/)
  assert.match(loginSrc, /safeNextPath/)
  // Garde anti-open-redirect : chemin interne uniquement, jamais protocole-relatif.
  assert.match(loginSrc, /!next\.startsWith\('\/'\)\s*\|\|\s*next\.startsWith\('\/\/'\)/)
  // VX46 a introduit le module d'atterrissage préféré : `?next=` reste PRIORITAIRE
  // (garde intacte), le repli n'est plus le `/dashboard` codé en dur.
  assert.match(loginSrc, /navigate\(next \|\| resolveLandingPath\(/)
})
