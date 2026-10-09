// ADEP19 (C-ADEP-021) — au démarrage, un `fetchMe` qui échoue SANS refus
// d'authentification (réseau, 503) ne redirige plus vers /login : les loaders
// rendent l'état « hors ligne » (écran HorsLigneDemarrage). Seul 401/403 redirige.
//
// node:test (la couche *.test.mjs de la CI ne sait pas charger du JSX) : le code
// RÉEL des loaders est extrait de `index.jsx` (de `bootstrapPromise` à la garde de
// module) et exécuté ; seule la frontière `store.dispatch(fetchMe())` est bouchonnée
// avec la forme de rejet posée par ADEP33 ({ status, reseau }).
// Test-du-test : remettre `return buildLoginRedirect(request)` sur tout échec ⇒ les
// cas réseau et 503 échouent.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import path from 'node:path'

const __dirname = path.dirname(fileURLToPath(import.meta.url))
const src = readFileSync(path.join(__dirname, 'index.jsx'), 'utf8')
const debut = src.indexOf('let bootstrapPromise = null')
const fin = src.indexOf('// ODX6 — Garde de MODULE')
assert.ok(debut > 0 && fin > debut, 'bloc des loaders introuvable dans index.jsx')
const bloc = src.slice(debut, fin)

function monter(rejet) {
  const etat = { isAuthenticated: false, user: null, role: null, permissions: [] }
  const fetchMe = () => ({ type: 'fetchMe' })
  fetchMe.fulfilled = { match: (r) => r.fulfilled === true }
  const store = {
    getState: () => ({ auth: etat }),
    dispatch: async () => {
      if (rejet) return { fulfilled: false, payload: rejet }
      etat.isAuthenticated = true
      etat.user = { portee: 'interne' }
      return { fulfilled: true, payload: etat.user }
    },
  }
  const redirect = (to) => ({ redirectTo: to })
  const fabrique = new Function(
    'store', 'fetchMe', 'redirect', 'portalHomePath', 'peutEntrerDansPortail',
    'cheminMotDePassePortail', 'estAutoriseEntree', 'resolveLandingFromAuth', 'URL',
    `${bloc}\nreturn { authLoader, rootLoader }`,
  )
  return fabrique(
    store, fetchMe, redirect, () => null, () => true, () => null, () => true,
    () => '/dashboard', URL,
  )
}

const requete = { request: { url: 'http://localhost/dashboard' } }

test('échec réseau : pas de redirection, état hors ligne', async () => {
  const { authLoader } = monter({ status: null, reseau: true })
  const res = await authLoader(requete)
  assert.deepEqual(res, { horsLigne: true })
})

test('503 : pas de redirection, état hors ligne', async () => {
  const { authLoader, rootLoader } = monter({ status: 503, reseau: false })
  assert.deepEqual(await authLoader(requete), { horsLigne: true })
  assert.deepEqual(await rootLoader(), { horsLigne: true })
})

test('401 et 403 : redirection vers /login avec ?next= comme avant', async () => {
  for (const status of [401, 403]) {
    const { authLoader } = monter({ status, reseau: false })
    const res = await authLoader(requete)
    assert.equal(res.redirectTo, `/login?next=${encodeURIComponent('/dashboard')}`)
  }
})

test('session valide : le loader laisse passer (null)', async () => {
  const { authLoader } = monter(null)
  assert.equal(await authLoader(requete), null)
})
