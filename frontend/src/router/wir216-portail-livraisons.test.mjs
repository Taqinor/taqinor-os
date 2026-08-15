// WIR216/XSTK22 — la section « Livraisons » du portail client doit être
// MONTÉE (route + nav), pas seulement le composant écrit. Vérification de
// SOURCE (pas de node_modules installés dans ce lane — cf. SigneDialog.test.mjs).
//   node --test src/router/wir216-portail-livraisons.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

const HERE = dirname(fileURLToPath(import.meta.url))
const ROUTER_SRC = readFileSync(join(HERE, 'index.jsx'), 'utf8')
const NAV_SRC = readFileSync(
  join(HERE, '..', 'features', 'portail', 'client', 'PortalClientLayout.jsx'), 'utf8')
const NOTIFY_SRC = readFileSync(
  join(HERE, '..', '..', '..', 'backend', 'django_core', 'apps', 'installations',
    'livraison_client_notify.py'), 'utf8')

test("route /portail/client/livraisons montee avec portalLoader(PORTEE_CLIENT)", () => {
  const bloc = ROUTER_SRC.slice(
    ROUTER_SRC.indexOf("path: '/portail/client/livraisons'"),
    ROUTER_SRC.indexOf("path: '/portail/client/livraisons'") + 250,
  )
  assert.match(bloc, /loader: portalLoader\(PORTEE_CLIENT\)/)
  assert.match(bloc, /PortalClientLayout/)
  assert.match(bloc, /PortailClientLivraisons/)
})

test('le lien de nav « Livraisons » existe dans PortalClientLayout', () => {
  assert.match(NAV_SRC, /to: '\/portail\/client\/livraisons', label: 'Livraisons'/)
})

test("_livraison_lien pointe vers /portail/client/livraisons, jamais l'ancienne route morte", () => {
  assert.match(NOTIFY_SRC, /path = '\/portail\/client\/livraisons'/)
  assert.doesNotMatch(NOTIFY_SRC, /\/portail\/livraisons\/\{livraison\.id\}/)
})
