// YJPB1 — Tests purs (node --test, aucune dépendance) du journal des problèmes
// vécus par les utilisateurs : normalisation de route sans donnée personnelle,
// forme exacte du corps, les trois règles absolues (jamais bloquant, jamais
// récursif, jamais un flot) et le tri des erreurs axios réellement vécues.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  GENRES, normaliserRoute, construireCorps, signalerProbleme,
  signalerErreurRequete, signalerErreurScript, _resetJournalPourTests,
} from './journalProblemes.js'

/** Dépendances injectées : session ouverte + fetch espion + horloge figée. */
function bancDEssai({ connecte = true, maintenant = 1_000_000 } = {}) {
  const envois = []
  return {
    envois,
    deps: {
      sessionEstActive: () => connecte,
      maintenant: () => maintenant,
      fetch: (url, options) => {
        envois.push({ url, corps: JSON.parse(options.body), options })
        return Promise.resolve({ status: 201 })
      },
    },
  }
}

test.beforeEach(() => {
  _resetJournalPourTests()
})

// ── Normalisation : aucune donnée personnelle ne part dans le journal ───────

test('normaliserRoute() retire la chaîne de requête (elle peut porter un nom, un e-mail)', () => {
  assert.equal(
    normaliserRoute('/api/django/crm/leads/?search=nabil.amar@example.com'),
    '/api/django/crm/leads/')
  assert.equal(normaliserRoute('/x/y#ancre'), '/x/y')
})

test('normaliserRoute() regroupe les identifiants sous <id> (500 devis = 1 ligne)', () => {
  assert.equal(
    normaliserRoute('/api/django/ventes/devis/1637/proposal/'),
    '/api/django/ventes/devis/<id>/proposal/')
  assert.equal(
    normaliserRoute('/api/django/ged/depot/3f2504e0-4f89-11d3-9a0c-0305e82c3301/'),
    '/api/django/ged/depot/<id>/')
  // Jeton long (lien public) : jamais conservé tel quel.
  assert.equal(
    normaliserRoute('/api/django/reporting/rapports-partages/abcdefghijklmnopqrstuvwxyz/'),
    '/api/django/reporting/rapports-partages/<id>/')
})

test('normaliserRoute() accepte une URL absolue et une entrée vide sans lever', () => {
  assert.equal(normaliserRoute('https://api.taqinor.ma/api/django/x/?a=1'),
    '/api/django/x/')
  assert.equal(normaliserRoute(''), '')
  assert.equal(normaliserRoute(undefined), '')
  assert.equal(normaliserRoute(null), '')
})

test('construireCorps() renvoie la forme exacte attendue par le serializer backend', () => {
  const corps = construireCorps({
    genre: GENRES.RESEAU,
    methode: 'get',
    route: '/api/django/crm/leads/42/?x=1',
    statut: null,
    code: 'ECONNABORTED',
    message: 'timeout of 20000ms exceeded',
  })
  assert.deepEqual(corps, {
    genre: 'reseau',
    methode: 'GET',
    route: '/api/django/crm/leads/<id>/',
    ecran: '',
    statut_http: null,
    code: 'ECONNABORTED',
    message: 'timeout of 20000ms exceeded',
  })
})

test('construireCorps() tronque aux tailles des colonnes (un signalement n\'est jamais perdu)', () => {
  const corps = construireCorps({
    genre: GENRES.SCRIPT,
    methode: 'PROPFINDX',
    code: 'C'.repeat(200),
    message: 'M'.repeat(900),
    statut: NaN,
  })
  assert.equal(corps.methode.length, 8)
  assert.equal(corps.code.length, 64)
  assert.equal(corps.message.length, 255)
  assert.equal(corps.statut_http, null)
})

// ── Règle 3 : jamais un flot ────────────────────────────────────────────────

test('signalerProbleme() n\'envoie RIEN hors session (sinon chaque problème ajoute un 401)', () => {
  const { envois, deps } = bancDEssai({ connecte: false })
  assert.equal(signalerProbleme({ genre: GENRES.RESEAU, route: '/x' }, deps), false)
  assert.equal(envois.length, 0)
})

test('signalerProbleme() poste une fois et dédoublonne le même problème dans la minute', () => {
  const { envois, deps } = bancDEssai()
  const probleme = { genre: GENRES.SERVEUR, methode: 'GET', route: '/x', statut: 500 }
  assert.equal(signalerProbleme(probleme, deps), true)
  assert.equal(signalerProbleme(probleme, deps), false)
  assert.equal(signalerProbleme(probleme, deps), false)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].url, '/api/django/reporting/problemes-client/')
  assert.equal(envois[0].options.method, 'POST')
  assert.equal(envois[0].options.keepalive, true)
  assert.equal(envois[0].options.credentials, 'include')
  assert.equal(envois[0].corps.statut_http, 500)
})

test('signalerProbleme() re-signale le même problème passée la fenêtre d\'une minute', () => {
  const { envois, deps } = bancDEssai({ maintenant: 1_000_000 })
  const probleme = { genre: GENRES.SERVEUR, methode: 'GET', route: '/x', statut: 500 }
  signalerProbleme(probleme, deps)
  signalerProbleme(probleme, { ...deps, maintenant: () => 1_000_000 + 60_001 })
  assert.equal(envois.length, 2)
})

test('signalerProbleme() plafonne les envois d\'un chargement de page (écran qui boucle)', () => {
  const { envois, deps } = bancDEssai()
  for (let i = 0; i < 200; i += 1) {
    signalerProbleme({ genre: GENRES.SCRIPT, route: '/x', code: `E${i}` }, deps)
  }
  assert.equal(envois.length, 40)
})

// ── Règles 1 et 2 : jamais bloquant, jamais récursif ───────────────────────

test('signalerProbleme() ne lève jamais, même si fetch explose', () => {
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    fetch: () => { throw new Error('réseau mort') },
  }
  assert.equal(signalerProbleme({ genre: GENRES.RESEAU, route: '/x' }, deps), false)
})

test('signalerProbleme() avale un rejet du POST (jamais de boucle de signalement)', async () => {
  let rejete = 0
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    fetch: () => { rejete += 1; return Promise.reject(new Error('offline')) },
  }
  assert.equal(signalerProbleme({ genre: GENRES.RESEAU, route: '/x' }, deps), true)
  await new Promise((r) => setTimeout(r, 0))
  assert.equal(rejete, 1)
})

test('signalerErreurRequete() ignore une erreur sur le journal lui-même', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/api/django/reporting/problemes-client/', method: 'post' },
    code: 'ERR_NETWORK',
  }, deps)
  assert.equal(envois.length, 0)
})

// ── Tri des erreurs axios : ce que l'utilisateur VIT réellement ─────────────

test('signalerErreurRequete() classe une requête sans réponse en « reseau » (délai 20 s)', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/crm/leads/', method: 'get' },
    code: 'ECONNABORTED',
    message: 'timeout of 20000ms exceeded',
  }, deps)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].corps.genre, 'reseau')
  assert.equal(envois[0].corps.statut_http, null)
  assert.equal(envois[0].corps.code, 'ECONNABORTED')
})

test('signalerErreurRequete() classe une 5xx en « serveur »', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/ventes/devis/12/', method: 'post' },
    response: { status: 502, data: {} },
    message: 'Request failed with status code 502',
  }, deps)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].corps.genre, 'serveur')
  assert.equal(envois[0].corps.statut_http, 502)
  assert.equal(envois[0].corps.route, '/ventes/devis/<id>/')
})

test('signalerErreurRequete() ignore les 4xx (refus compris) et les annulations', () => {
  const { envois, deps } = bancDEssai()
  for (const statut of [400, 401, 403, 404, 409, 429]) {
    signalerErreurRequete({
      config: { url: '/x/', method: 'get' }, response: { status: statut },
    }, deps)
  }
  signalerErreurRequete({ config: { url: '/y/' }, code: 'ERR_CANCELED' }, deps)
  assert.equal(envois.length, 0)
})

test('signalerErreurScript() signale une vraie erreur JS et ignore une erreur axios', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurScript(new TypeError("Cannot read properties of undefined"), undefined, deps)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].corps.genre, 'script')
  assert.equal(envois[0].corps.code, 'TypeError')
  assert.equal(envois[0].corps.route, '')

  // Déjà signalée par l'intercepteur, avec sa route : jamais deux fois.
  const axiosErreur = new Error('Network Error')
  axiosErreur.isAxiosError = true
  axiosErreur.config = { url: '/crm/leads/' }
  assert.equal(signalerErreurScript(axiosErreur, undefined, deps), false)
  assert.equal(envois.length, 1)
})

test('signalerErreurScript() accepte le genre « ecran » (error boundary)', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurScript(new Error('boom'), GENRES.ECRAN, deps)
  assert.equal(envois[0].corps.genre, 'ecran')
})

// ── Gardes de câblage ───────────────────────────────────────────────────────

test("ce module n'importe JAMAIS session-bridge (son BroadcastChannel garde node --test en vie)", () => {
  const source = readFileSync(new URL('./journalProblemes.js', import.meta.url), 'utf8')
  assert.doesNotMatch(source, /from '.*session-bridge/)
})

test('les deux appelants réels injectent le lecteur de session (sinon journal muet)', () => {
  const axios = readFileSync(new URL('../api/axios.js', import.meta.url), 'utf8')
  assert.match(axios, /signalerErreurRequete\(error, \{ sessionEstActive \}\)/)
  const globaux = readFileSync(new URL('./globalErrors.js', import.meta.url), 'utf8')
  assert.match(globaux, /signalerErreurScript\(error, undefined, \{ sessionEstActive \}\)/)
})

test("sans lecteur de session injecté, rien n'est envoyé (jamais un 401 de plus)", () => {
  let appels = 0
  assert.equal(signalerProbleme(
    { genre: GENRES.RESEAU, route: '/x' },
    { fetch: () => { appels += 1; return Promise.resolve({}) }, maintenant: () => 1 },
  ), false)
  assert.equal(appels, 0)
})
