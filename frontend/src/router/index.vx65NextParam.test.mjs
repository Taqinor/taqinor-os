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

// NTPRT8 — `authLoader`/`roleLoader` résolvent désormais la PORTÉE du compte
// (`ensurePortalScope`, qui enveloppe `ensureSession`) avant de décider : la
// session absente renvoie `null`, et c'est ce cas qui déclenche
// `buildLoginRedirect(request)`. L'invariant VX65 (capture du `Request` →
// /login?next=…) est INCHANGÉ ; seule la forme de la garde a bougé.
test('authLoader capture le Request et construit une redirection /login?next=... via buildLoginRedirect', () => {
  assert.match(routerSrc, /const authLoader = async \(\{\s*request\s*\}\)\s*=>/)
  assert.match(routerSrc, /if \(!user\) return buildLoginRedirect\(request\)/)
  assert.match(routerSrc, /redirect\(`\/login\?next=\$\{encodeURIComponent\(next\)\}`\)/)
})

test('roleLoader capture aussi le Request pour rediriger via buildLoginRedirect', () => {
  assert.match(
    routerSrc,
    /const roleLoader = \(roles, perm\) => async \(\{\s*request\s*\}\)\s*=>/,
  )
  assert.match(routerSrc, /if \(!user\) return buildLoginRedirect\(request\)/)
})

test("Login.jsx lit '?next=' via useSearchParams et le suit seulement s'il est sûr", () => {
  assert.match(loginSrc, /useSearchParams/)
  assert.match(loginSrc, /safeNextPath/)
  // Garde anti-open-redirect : chemin interne uniquement, jamais protocole-relatif.
  assert.match(loginSrc, /!next\.startsWith\('\/'\)\s*\|\|\s*next\.startsWith\('\/\/'\)/)
  // VX46 a introduit le module d'atterrissage préféré : `?next=` reste PRIORITAIRE
  // (garde intacte), le repli n'est plus le `/dashboard` codé en dur.
  // ODY3 — la résolution est passée dans `lib/apps/landing.js` (préférence VX46
  // → dernier module VX11 → mono-app → Menu d'accueil `/apps`), partagée avec la
  // garde `/` du routeur ; `?next=` garde exactement la même priorité.
  assert.match(loginSrc, /navigate\(next \|\| resolveLandingFromAuth\(/)
})
