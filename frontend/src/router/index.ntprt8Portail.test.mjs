// NTPRT8 — Vérification structurelle (node --test, même patron que VX64/VX65/
// VX78 : pas de vitest/jsdom dans les worktrees d'agents) du câblage de la
// FRONTIÈRE portail externe ⟷ ERP interne dans le routeur.
//
// Ce qui est verrouillé ici est exactement le critère d'acceptation NTPRT8 :
// « un compte client ne peut jamais naviguer manuellement vers une route
// interne (redirection automatique) ». Concrètement, les DEUX loaders qui
// gardent les routes internes (`authLoader` et `roleLoader`) doivent renvoyer
// un compte portail vers son shell, et le catch-all doit faire de même.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const routerSrc = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const scopeSrc = readFileSync(
  path.join(__dirname, '..', 'features', 'portail', 'portalScope.js'),
  'utf8',
)

test('le routeur lit la portée depuis la source UNIQUE features/portail/portalScope', () => {
  assert.match(
    routerSrc,
    /from '\.\.\/features\/portail\/portalScope'/,
    'la portée ne doit jamais être ré-implémentée dans le routeur',
  )
  assert.match(scopeSrc, /export function portalHomePath/)
  assert.match(scopeSrc, /export function peutEntrerDansPortail/)
})

test('la portée est RÉSOLUE (fetchMe) avant toute décision de garde', () => {
  // Au retour de /token/ le store ne porte que { username } : décider sur un
  // `portee` encore `undefined` laisserait un compte portail atteindre l'ERP.
  assert.match(routerSrc, /const ensurePortalScope = async \(\) => \{/)
  assert.match(routerSrc, /if \(!user \|\| user\.portee === undefined\) \{/)
  assert.match(routerSrc, /await store\.dispatch\(fetchMe\(\)\)/)
})

test('authLoader renvoie un compte portail vers son shell (jamais vers l’ERP)', () => {
  const bloc = routerSrc.match(
    /const authLoader = async \(\{ request \}\) => \{[\s\S]*?\n\}/,
  )
  assert.ok(bloc, 'authLoader doit exister')
  assert.match(bloc[0], /await ensurePortalScope\(\)/)
  assert.match(bloc[0], /redirectSiPortail\(user\)/)
})

test('roleLoader applique la MÊME bascule avant le contrôle de rôle', () => {
  const bloc = routerSrc.match(
    /const roleLoader = \(roles, perm\) => async \(\{ request \}\) => \{[\s\S]*?\n\}/,
  )
  assert.ok(bloc, 'roleLoader doit exister')
  assert.match(bloc[0], /await ensurePortalScope\(\)/)
  assert.match(
    bloc[0],
    /const versPortail = redirectSiPortail\(user\)[\s\S]*?if \(versPortail\) return versPortail/,
    'la bascule portail doit précéder le contrôle de rôle',
  )
})

test('le catch-all bascule un compte portail connecté, sans exiger de session', () => {
  assert.match(routerSrc, /const notFoundLoader = async \(\) => \{/)
  // Un anonyme doit toujours voir le 404 (pas de redirection vers /login).
  assert.match(routerSrc, /if \(!isAuthenticated\) return null/)
  assert.match(routerSrc, /\{ path: '\*', loader: notFoundLoader,/)
})

test('la route /portail/client exige la portée EXACTE portail_client', () => {
  assert.match(routerSrc, /path: '\/portail\/client',/)
  assert.match(routerSrc, /loader: portalLoader\(PORTEE_CLIENT\)/)
  const bloc = routerSrc.match(
    /const portalLoader = \(portee\) => async \(\{ request \}\) => \{[\s\S]*?\n\}/,
  )
  assert.ok(bloc, 'portalLoader doit exister')
  assert.match(bloc[0], /if \(peutEntrerDansPortail\(user, portee\)\) return null/)
})

test('le shell portail n’est PAS le shell ERP (pas de WithLayout)', () => {
  const ligne = routerSrc
    .split('\n')
    .find((l) => /path: '\/portail\/client'/.test(l))
  assert.ok(ligne, "la route '/portail/client' doit être déclarée")
  const bloc = routerSrc.match(
    /path: '\/portail\/client',[\s\S]*?\n  \},/,
  )
  assert.ok(bloc)
  assert.doesNotMatch(
    bloc[0], /WithLayout/,
    'un compte externe ne doit jamais recevoir la coquille ERP interne',
  )
  assert.match(bloc[0], /WithPortal shell=\{PortalClientLayout\}/)
})
