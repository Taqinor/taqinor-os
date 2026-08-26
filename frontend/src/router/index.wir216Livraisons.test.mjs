// WIR216 — « Mes livraisons » du portail client : le lien de l'email de
// livraison (FG228/XSTK22, apps.installations.livraison_client_notify)
// pointait vers une section INEXISTANTE (404 systématique). Vérification de
// SOURCE (pas de node_modules dans ce lane — même patron que
// index.ntprt8Portail.test.mjs / demandes-adhoc-wir62.test.mjs).
//   node --test src/router/index.wir216Livraisons.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROUTER = readFileSync(join(HERE, 'index.jsx'), 'utf8')
const LAYOUT = readFileSync(
  join(HERE, '..', 'features', 'portail', 'client', 'PortalClientLayout.jsx'), 'utf8')
const PAGE = readFileSync(
  join(HERE, '..', 'features', 'portail', 'client', 'PortailClientLivraisons.jsx'), 'utf8')
const API = readFileSync(join(HERE, '..', 'api', 'portailApi.js'), 'utf8')

test('le routeur déclare /portail/client/livraisons avec le shell portail (jamais le shell ERP)', () => {
  assert.match(
    ROUTER,
    /const PortailClientLivraisons = lazy\(\(\) => import\('\.\.\/features\/portail\/client\/PortailClientLivraisons'\)\)/,
  )
  const bloc = ROUTER.match(
    /path: '\/portail\/client\/livraisons',[\s\S]*?\n  \},/,
  )
  assert.ok(bloc, "la route '/portail/client/livraisons' doit être déclarée")
  assert.match(bloc[0], /loader: portalLoader\(PORTEE_CLIENT\)/)
  assert.match(bloc[0], /WithPortal shell=\{PortalClientLayout\}/)
  assert.doesNotMatch(
    bloc[0], /WithLayout/,
    'un compte portail ne doit jamais recevoir la coquille ERP interne',
  )
})

test('la nav du portail client propose « Livraisons »', () => {
  assert.match(LAYOUT, /to: '\/portail\/client\/livraisons', label: 'Livraisons'/)
})

test('portailApi expose la lecture des livraisons (scopée serveur)', () => {
  assert.match(API, /livraisons:\s*\{\s*liste:\s*\(\)\s*=>\s*api\.get\('\/portail\/mes-livraisons\/'\)/)
})

test('PortailClientLivraisons charge via portailApi.livraisons.liste (jamais un id de client envoyé)', () => {
  assert.match(PAGE, /portailApi\.livraisons\.liste\(\)/)
  assert.doesNotMatch(
    PAGE, /client_id|clientId/,
    'le scope vient du compte connecté côté serveur — jamais un paramètre client depuis le front',
  )
})
