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

function monter(rejet, { enLigne = true } = {}) {
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
    'cheminMotDePassePortail', 'estAutoriseEntree', 'resolveLandingFromAuth', 'URL', 'navigator',
    `${bloc}\nreturn { authLoader, rootLoader }`,
  )
  return fabrique(
    store, fetchMe, redirect, () => null, () => true, () => null, () => true,
    () => '/dashboard', URL, { onLine: enLigne },
  )
}

const requete = { request: { url: 'http://localhost/dashboard' } }

test('échec réseau : pas de redirection, état hors ligne', async () => {
  const { authLoader } = monter({ status: null, reseau: true })
  const res = await authLoader(requete)
  assert.deepEqual(res, { horsLigne: true })
})

// J3 — un serveur qui RÉPOND (5xx) ou qui répond LENTEMENT (délai dépassé) n'est pas « hors ligne ».
test('503 : pas de redirection, état « serveur lent » (le serveur a répondu)', async () => {
  const { authLoader, rootLoader } = monter({ status: 503, reseau: false, expire: false })
  assert.deepEqual(await authLoader(requete), { horsLigne: true, lent: true })
  assert.deepEqual(await rootLoader(), { horsLigne: true, lent: true })
})

test('J3 — délai dépassé, navigateur en ligne : « serveur lent », jamais « Hors ligne »', async () => {
  const { authLoader } = monter({ status: null, reseau: true, expire: true })
  assert.deepEqual(await authLoader(requete), { horsLigne: true, lent: true })
})

test('J3 — délai dépassé, navigateur HORS LIGNE : état hors ligne (vrai hors ligne inchangé)', async () => {
  const { authLoader } = monter({ status: null, reseau: true, expire: true }, { enLigne: false })
  assert.deepEqual(await authLoader(requete), { horsLigne: true })
})

test("J3 — l'écran de démarrage a deux textes : hors ligne, et serveur lent avec nouvel essai seul", () => {
  const ecran = readFileSync(path.join(__dirname, 'HorsLigneDemarrage.jsx'), 'utf8')
  assert.match(ecran, /titre: 'Le serveur met du temps à répondre'/)
  assert.match(ecran, /bouton: 'Réessayer'/)
  assert.match(ecran, /titre: 'Hors ligne',/)
  assert.match(ecran, /Impossible de joindre le serveur\./)
  assert.match(ecran, /const lent = useLoaderData\(\)\?\.lent === true/)
  assert.match(ecran, /setTimeout\(\(\) => reessayerRef\.current\(\), DELAI_NOUVEL_ESSAI_MS\)/)
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
