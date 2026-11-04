// VX72 — Sentry frontend no-op DSN-gaté (miroir de core/monitoring.py côté
// backend). Sans VITE_SENTRY_DSN (le cas ici, plain Node sans Vite —
// import.meta.env est undefined) : no-op total, jamais d'exception, jamais
// d'import de @sentry/react (la garde DSN sort avant l'import dynamique).
// Exécuté en CI : node --test src/lib/monitoring.test.mjs
//
// YJPB1 — ce module couvre AUSSI `lib/journalProblemes.js` (seconde moitié du
// fichier) : c'est le journal maison des problèmes vécus, qui existe
// précisément parce que le chemin Sentry testé ci-dessus est un no-op total
// sans DSN. Les deux sont la même surface « monitoring d'erreurs frontend »,
// et `check_test_placement` (AMET84) refuse un fichier de test neuf par tâche.
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  sentryDsn, isMonitoringEnabled, initMonitoring, captureException, bindCompany,
  suivreSocieteDuStore,
} from './monitoring.js'
import {
  GENRES, normaliserRoute, construireCorps, signalerProbleme,
  signalerErreurRequete, signalerErreurScript, installerRechargementChunk,
  _resetJournalPourTests, _nombreSignaturesPourTests,
} from './journalProblemes.js'

test('QAH8 : import @sentry/react LITTÉRAL (un specifier variable n\'est jamais bundlé par Vite → Sentry mort en prod)', () => {
  const src = readFileSync(new URL('./monitoring.js', import.meta.url), 'utf8')
  assert.match(src, /await import\('@sentry\/react'\)/)
  assert.doesNotMatch(src, /@vite-ignore/)
})

test('QAH8 : suivreSocieteDuStore suit la société (login, changement, logout) sans rappel inutile', () => {
  let etat = { auth: { user: null } }
  const abonnes = []
  const store = {
    getState: () => etat,
    subscribe: (fn) => { abonnes.push(fn); return () => {} },
  }
  const desabonner = suivreSocieteDuStore(store)
  assert.equal(typeof desabonner, 'function')
  assert.equal(abonnes.length, 1)
  for (const user of [{ active_company_id: 7 }, { active_company_id: 7 }, { company_id: 9 }, null]) {
    etat = { auth: { user } }
    assert.doesNotThrow(() => abonnes[0]())
  }
})

test('sans DSN (import.meta.env absent en plain Node) : sentryDsn() vide, monitoring désactivé', () => {
  assert.equal(sentryDsn(), '')
  assert.equal(isMonitoringEnabled(), false)
})

test('sans DSN : initMonitoring() ne lève jamais et renvoie false (no-op)', async () => {
  const ok = await initMonitoring()
  assert.equal(ok, false)
})

test('sans DSN : captureException() ne lève jamais et renvoie null (aucun envoi)', async () => {
  const eventId = await captureException(new Error('test'), { extra: 'contexte' })
  assert.equal(eventId, null)
})

test('captureException() tolère une erreur non-Error (jamais de crash du reporting lui-même)', async () => {
  const eventId = await captureException('juste une chaîne')
  assert.equal(eventId, null)
})

// QAH8 — bindCompany(), pendant React de core.monitoring.bind_company (Django).
test('bindCompany() sans DSN/SDK chargé ne lève jamais (no-op, valeur seulement mémorisée)', () => {
  assert.doesNotThrow(() => bindCompany(42))
})

test('bindCompany() tolère null (effacement du tag, ex. déconnexion)', () => {
  assert.doesNotThrow(() => bindCompany(null))
})

test('bindCompany() puis captureException() sans DSN : toujours no-op total', async () => {
  bindCompany(7)
  const eventId = await captureException(new Error('test'))
  assert.equal(eventId, null)
})


// ═══════════════════════════════════════════════════════════════════════════
// YJPB1 — journal des problèmes vécus par les utilisateurs
// (`lib/journalProblemes.js`) : normalisation de route sans donnée
// personnelle, forme exacte du corps, les trois règles absolues (jamais
// bloquant, jamais récursif, jamais un flot) et le tri des erreurs axios
// réellement vécues.
// ═══════════════════════════════════════════════════════════════════════════


/** Dépendances injectées : session ouverte + fetch espion + horloge figée. */
function bancDEssai({ connecte = true, maintenant = 1_000_000 } = {}) {
  _resetJournalPourTests()
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

test('normaliserRoute() ne masque jamais un slug de route kebab-case, même long', () => {
  assert.equal(
    normaliserRoute('/api/django/reporting/approbations-en-attente/'),
    '/api/django/reporting/approbations-en-attente/')
  assert.equal(
    normaliserRoute('/achats/bons-commande-fournisseur/12/recevoir/'),
    '/achats/bons-commande-fournisseur/<id>/recevoir/')
  // Un jeton de partage (token_urlsafe) porte aussi des tirets : il reste masqué.
  assert.equal(
    normaliserRoute('/proposal/Xy7-kQ2_mN9pLw4Rt8Zb-Vc3Hs6Jd1Fg/'),
    '/proposal/<id>/')
  assert.equal(
    normaliserRoute('/proposal/3f2504e04f8911d39a0c0305e82c3301/'),
    '/proposal/<id>/')
  // Des chiffres hexadécimaux coupés par des tirets ne font pas un slug.
  assert.equal(
    normaliserRoute('/x/a1b2c3d4-e5f6a7b8-c9d0e1f2/'),
    '/x/<id>/')
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
    statut_reponse: null,
    code: 'ECONNABORTED',
    message: 'timeout of 20000ms exceeded',
    request_id: null,
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
  assert.equal(corps.statut_reponse, null)
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
  assert.equal(envois[0].corps.statut_reponse, 500)
})

test('signalerProbleme() re-signale le même problème passée la fenêtre d\'une minute', () => {
  const { envois, deps } = bancDEssai({ maintenant: 1_000_000 })
  const probleme = { genre: GENRES.SERVEUR, methode: 'GET', route: '/x', statut: 500 }
  signalerProbleme(probleme, deps)
  signalerProbleme(probleme, { ...deps, maintenant: () => 1_000_000 + 60_001 })
  assert.equal(envois.length, 2)
})

test('signalerProbleme() plafonne les envois d\'une tranche (écran qui boucle)', () => {
  const { envois, deps } = bancDEssai()
  for (let i = 0; i < 200; i += 1) {
    signalerProbleme({ genre: GENRES.SCRIPT, route: '/x', code: `E${i}` }, deps)
  }
  assert.equal(envois.length, 40)
})

test('plafond par tranche de 10 min : un onglet ouvert toute la journée ne devient pas muet', () => {
  let horloge = 1_000_000
  const { envois, deps } = bancDEssai()
  const avecHorloge = { ...deps, maintenant: () => horloge }
  for (let i = 0; i < 60; i += 1) {
    signalerProbleme({ genre: GENRES.SERVEUR, route: `/x${i}`, statut: 502 }, avecHorloge)
  }
  assert.equal(envois.length, 40)
  horloge += 9 * 60_000
  assert.equal(signalerProbleme({ genre: GENRES.SERVEUR, route: '/encore', statut: 502 }, avecHorloge), false)
  horloge += 60_000
  assert.equal(signalerProbleme({ genre: GENRES.SERVEUR, route: '/apres', statut: 502 }, avecHorloge), true)
  assert.equal(envois.length, 41)
})

test("les signatures expirées sont purgées (la mémoire de l'onglet ne grossit pas)", () => {
  let horloge = 1_000_000
  const { deps } = bancDEssai()
  const avecHorloge = { ...deps, maintenant: () => horloge }
  for (let i = 0; i < 30; i += 1) {
    signalerProbleme({ genre: GENRES.SERVEUR, route: `/x${i}`, statut: 502 }, avecHorloge)
  }
  assert.equal(_nombreSignaturesPourTests(), 30)
  horloge += 10 * 60_000
  signalerProbleme({ genre: GENRES.SERVEUR, route: '/y', statut: 502 }, avecHorloge)
  assert.equal(_nombreSignaturesPourTests(), 1)
})

// ── Règles 1 et 2 : jamais bloquant, jamais récursif ───────────────────────

test('signalerProbleme() ne lève jamais, même si fetch explose', () => {
  _resetJournalPourTests()
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    fetch: () => { throw new Error('réseau mort') },
  }
  assert.equal(signalerProbleme({ genre: GENRES.RESEAU, route: '/x' }, deps), false)
})

test('signalerProbleme() avale un rejet du POST (jamais de boucle de signalement)', async () => {
  _resetJournalPourTests()
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

// ── ERR-JPB-BALISE-401-APRES-30-MIN : la ligne survit au cookie expiré ──────

const attendreMicrotaches = () => new Promise((r) => setTimeout(r, 0))

test('balise : sur 401, UN refresh puis UN second envoi du même corps', async () => {
  _resetJournalPourTests()
  const envois = []
  let refreshes = 0
  const reponses = [{ status: 401 }, { status: 201 }]
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    rafraichir: () => { refreshes += 1; return Promise.resolve() },
    fetch: (url, options) => { envois.push(options.body); return Promise.resolve(reponses.shift()) },
  }
  assert.equal(signalerProbleme({ genre: GENRES.SCRIPT, code: 'TypeError' }, deps), true)
  await attendreMicrotaches()
  assert.equal(refreshes, 1)
  assert.equal(envois.length, 2)
  assert.equal(envois[0], envois[1])
})

test('balise : un 401 persistant ne boucle jamais', async () => {
  _resetJournalPourTests()
  let envois = 0
  let refreshes = 0
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    rafraichir: () => { refreshes += 1; return Promise.resolve() },
    fetch: () => { envois += 1; return Promise.resolve({ status: 401 }) },
  }
  signalerProbleme({ genre: GENRES.SCRIPT, code: 'TypeError' }, deps)
  await attendreMicrotaches()
  assert.equal(refreshes, 1)
  assert.equal(envois, 2)
})

test('balise : un refresh en échec est avalé, sans second envoi ni signalement', async () => {
  _resetJournalPourTests()
  let envois = 0
  const deps = {
    sessionEstActive: () => true,
    maintenant: () => 1,
    rafraichir: () => Promise.reject(new Error('refresh mort')),
    fetch: () => { envois += 1; return Promise.resolve({ status: 401 }) },
  }
  assert.equal(signalerProbleme({ genre: GENRES.SCRIPT, code: 'TypeError' }, deps), true)
  await attendreMicrotaches()
  assert.equal(envois, 1)
})

test("balise : tout autre statut ne déclenche aucun refresh", async () => {
  for (const status of [201, 403, 429, 500]) {
    _resetJournalPourTests()
    let refreshes = 0
    const deps = {
      sessionEstActive: () => true,
      maintenant: () => 1,
      rafraichir: () => { refreshes += 1; return Promise.resolve() },
      fetch: () => Promise.resolve({ status }),
    }
    signalerProbleme({ genre: GENRES.SCRIPT, code: 'TypeError' }, deps)
    await attendreMicrotaches()
    assert.equal(refreshes, 0, String(status))
  }
})

test('balise : le refresh par défaut est la promesse PARTAGÉE (jamais un second POST en rotation)', () => {
  const source = readFileSync(new URL('./journalProblemes.js', import.meta.url), 'utf8')
  assert.match(source, /deps\.rafraichir \|\| refreshSession/)
  assert.match(source, /from '\.\.\/api\/refreshCoordinator\.js'/)
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
  assert.equal(envois[0].corps.statut_reponse, null)
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
  assert.equal(envois[0].corps.statut_reponse, 502)
  assert.equal(envois[0].corps.route, '/ventes/devis/<id>/')
})

// ── ERR-JPB-REQUEST-ID-PERDU : relier une ligne `serveur` à sa trace ────────

const ID_REQUETE = '0123456789abcdef0123456789abcdef'

test("signalerErreurRequete() lit le request_id dans l'en-tête X-Request-Id", () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/x/', method: 'get' },
    response: { status: 500, headers: { 'x-request-id': ID_REQUETE }, data: {} },
  }, deps)
  assert.equal(envois[0].corps.request_id, ID_REQUETE)
})

test('signalerErreurRequete() se rabat sur error.request_id du corps', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/x/', method: 'get' },
    response: { status: 500, headers: {}, data: { error: { code: 'e', request_id: ID_REQUETE } } },
  }, deps)
  assert.equal(envois[0].corps.request_id, ID_REQUETE)
})

test("un 502 sans Django, ou un identifiant illisible, laisse request_id nul (la ligne part)", () => {
  for (const reponse of [
    { status: 502, data: '<html>' },
    { status: 500, headers: { 'x-request-id': 'pas-un-id' }, data: {} },
  ]) {
    const { envois, deps } = bancDEssai()
    signalerErreurRequete({ config: { url: '/x/', method: 'get' }, response: reponse }, deps)
    assert.equal(envois.length, 1)
    assert.equal(envois[0].corps.request_id, null)
  }
})

test('nginx journalise le request_id de Django (un 502 sans rid = Django absent)', () => {
  const conf = readFileSync(new URL('../../../backend/nginx/nginx.conf', import.meta.url), 'utf8')
  assert.match(conf, /rid=\$upstream_http_x_request_id/)
})

test('signalerErreurRequete() journalise le 429 du refresh de session (seul 4xx concerné)', () => {
  const { envois, deps } = bancDEssai()
  signalerErreurRequete({
    config: { url: '/api/django/auth/token/refresh/', method: 'post' },
    response: { status: 429 },
  }, deps)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].corps.genre, 'serveur')
  assert.equal(envois[0].corps.statut_reponse, 429)
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
  _resetJournalPourTests()
  let appels = 0
  assert.equal(signalerProbleme(
    { genre: GENRES.RESEAU, route: '/x' },
    { fetch: () => { appels += 1; return Promise.resolve({}) }, maintenant: () => 1 },
  ), false)
  assert.equal(appels, 0)
})

// ── ERR-JPB-ECRAN-JAMAIS-EMIS : un écran tombé laisse enfin une ligne ───────

test('les deux error boundaries signalent le genre « ecran » avec le lecteur de session', () => {
  for (const chemin of ['../components/RouteErrorBoundary.jsx', '../ui/ErrorBoundary.jsx']) {
    const source = readFileSync(new URL(chemin, import.meta.url), 'utf8')
    assert.match(source, /signalerErreurScript\(error, GENRES\.ECRAN, \{ sessionEstActive \}\)/, chemin)
    // Le journal passe AVANT Sentry : c'est lui qui survit sans DSN.
    assert.ok(
      source.indexOf('signalerErreurScript(error') < source.indexOf('captureException(error'),
      chemin)
  }
})

test('main.jsx arme le rechargement de chunk avec le lecteur de session', () => {
  const source = readFileSync(new URL('../main.jsx', import.meta.url), 'utf8')
  assert.match(source, /installerRechargementChunk\(\{ sessionEstActive \}\)/)
})

test('un écran tombé sur un chunk introuvable porte le code ChunkLoadError', () => {
  for (const message of [
    'Failed to fetch dynamically imported module: https://x/assets/a.js',
    'error loading dynamically imported module',
    'Importing a module script failed.',
    'Unable to preload CSS for /assets/a.css',
    // `preventDefault` de Vite : lazy() résout undefined avant le rechargement.
    'Minified React error #306; visit https://react.dev/errors/306',
  ]) {
    const { envois, deps } = bancDEssai()
    signalerErreurScript(new TypeError(message), GENRES.ECRAN, deps)
    assert.equal(envois[0].corps.genre, 'ecran')
    assert.equal(envois[0].corps.code, 'ChunkLoadError', message)
  }
})

/** Fenêtre + stockage factices pour `vite:preloadError`. */
function bancChunk(stockageInitial = {}, { stockageCasse = false } = {}) {
  const ecouteurs = {}
  const valeurs = { ...stockageInitial }
  const banc = {
    recharges: 0,
    valeurs,
    cible: { addEventListener: (nom, fn) => { ecouteurs[nom] = fn } },
    stockage: {
      getItem: (cle) => { if (stockageCasse) throw new Error('privé'); return valeurs[cle] ?? null },
      setItem: (cle, valeur) => { if (stockageCasse) throw new Error('privé'); valeurs[cle] = valeur },
    },
    recharger: () => { banc.recharges += 1 },
    emettre: () => {
      const event = {
        payload: new Error('Failed to fetch dynamically imported module'),
        empeche: false,
        preventDefault() { this.empeche = true },
      }
      ecouteurs['vite:preloadError'](event)
      return event
    },
  }
  return banc
}

test('vite:preloadError : une ligne ecran ChunkLoadError et UN rechargement', () => {
  const { envois, deps } = bancDEssai({ maintenant: 500_000 })
  const banc = bancChunk()
  installerRechargementChunk({ ...deps, cible: banc.cible, stockage: banc.stockage, recharger: banc.recharger })
  const event = banc.emettre()
  assert.equal(banc.recharges, 1)
  assert.equal(event.empeche, true)
  assert.equal(envois.length, 1)
  assert.equal(envois[0].corps.genre, 'ecran')
  assert.equal(envois[0].corps.code, 'ChunkLoadError')
})

test('vite:preloadError : jamais une boucle — déjà rechargé récemment, la boundary prend le relais', () => {
  const { deps } = bancDEssai({ maintenant: 500_000 })
  const banc = bancChunk()
  const options = { ...deps, cible: banc.cible, stockage: banc.stockage, recharger: banc.recharger }
  installerRechargementChunk(options)
  banc.emettre()
  const seconde = banc.emettre()
  assert.equal(banc.recharges, 1)
  assert.equal(seconde.empeche, false)
})

test("vite:preloadError : stockage indisponible → aucun rechargement (la boucle est pire que l'écran)", () => {
  const { envois, deps } = bancDEssai()
  const banc = bancChunk({}, { stockageCasse: true })
  installerRechargementChunk({ ...deps, cible: banc.cible, stockage: banc.stockage, recharger: banc.recharger })
  const event = banc.emettre()
  assert.equal(banc.recharges, 0)
  assert.equal(event.empeche, false)
  assert.equal(envois.length, 1)
})

test('installerRechargementChunk() est inerte sans window (node, SSR)', () => {
  assert.doesNotThrow(() => installerRechargementChunk({ cible: null }))
})
