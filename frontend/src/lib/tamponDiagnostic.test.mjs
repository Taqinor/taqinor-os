// COP-D3 — tampon de diagnostic du navigateur. `node --test src/lib/tamponDiagnostic.test.mjs`
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import {
  MAX_ERREURS, MAX_REQUETES, instantaneDiagnostic, nettoyerMessage, normaliserRoute,
  noterErreur, noterRequete, viderTampon,
} from './tamponDiagnostic.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const CONTRAT = JSON.parse(readFileSync(
  join(HERE, '../../../backend/django_core/apps/agent/contract_samples/assistant_reponse.json'), 'utf8'))
const EXEMPLE = CONTRAT.diagnostic.exemple

test.beforeEach(() => viderTampon())

test('routes : identifiants, UUID, jetons, origine et chaîne de requête disparaissent', () => {
  assert.equal(normaliserRoute('/api/django/crm/leads/1637/'), '/api/django/crm/leads/<id>/')
  assert.equal(
    normaliserRoute('/api/django/ventes/devis/3f2b8c1e-0a4d-4e0b-9f3a-1c2d3e4f5a6b/proposal/'),
    '/api/django/ventes/devis/<id>/proposal/')
  assert.equal(normaliserRoute('/api/django/portail/AbCdEf0123456789XyZ_-token/'), '/api/django/portail/<id>/')
  assert.equal(normaliserRoute('/api/django/crm/leads/?search=Jean%20Dupont&email=a@b.ma'), '/api/django/crm/leads/')
  assert.equal(normaliserRoute('https://api.taqinor.ma/api/django/crm/leads/12/?x=1#f'), '/api/django/crm/leads/<id>/')
  assert.equal(normaliserRoute('/api/django/crm/relance-etapes/9/fait/'), '/api/django/crm/relance-etapes/<id>/fait/')
  assert.equal(normaliserRoute(undefined), '')
})

test('anneau des requêtes borné à 15, les plus anciennes sortent', () => {
  for (let i = 0; i < MAX_REQUETES + 5; i += 1) noterRequete({ methode: 'get', url: '/a/', statut: 200, dureeMs: i })
  const { requetes } = instantaneDiagnostic()
  assert.equal(requetes.length, 15)
  assert.equal(requetes[0].duree_ms, MAX_REQUETES + 4, 'la plus récente d\'abord')
  assert.equal(requetes[14].duree_ms, 5)
})

test('anneau des erreurs borné à 10', () => {
  for (let i = 0; i < MAX_ERREURS + 4; i += 1) noterErreur({ genre: 'script', message: `e${i}` })
  const { erreurs } = instantaneDiagnostic()
  assert.equal(erreurs.length, 10)
  assert.equal(erreurs[0].message, 'e13')
})

test('messages : e-mail, téléphone, suites de chiffres retirés ; tronqué à 200', () => {
  const m = nettoyerMessage('Échec pour jean.dupont@exemple.ma tel +212 6 12 34 56 78 ref 123456789')
  assert.ok(!m.includes('@') && !/\d{5}/.test(m) && !m.includes('212'), m)
  assert.equal(nettoyerMessage('x'.repeat(500)).length, 200)
  noterErreur({ genre: 'script', message: 'a@b.ma' })
  assert.ok(!JSON.stringify(instantaneDiagnostic()).includes('a@b.ma'))
})

test('requête : jamais de corps ni de chaîne de requête ; request_id et code filtrés', () => {
  noterRequete({
    methode: 'post', url: '/api/django/crm/leads/5/?tel=0612345678', statut: 409, dureeMs: 212.4,
    requestId: '0123456789abcdef0123456789abcdef', code: 'deja_fait',
  })
  noterRequete({ methode: 'get', url: '/x/', statut: 500, requestId: 'pas-un-id', code: 'un message long avec espaces' })
  const [b, a] = instantaneDiagnostic().requetes
  assert.deepEqual(Object.keys(a).sort(), Object.keys(EXEMPLE.requetes[0]).sort())
  assert.equal(a.methode, 'POST')
  assert.equal(a.route, '/api/django/crm/leads/<id>/')
  assert.equal(a.duree_ms, 212)
  assert.equal(a.request_id, '0123456789abcdef0123456789abcdef')
  assert.equal(a.code, 'deja_fait')
  assert.equal(b.request_id, '')
  assert.equal(b.code, '')
  assert.ok(!JSON.stringify(a).includes('0612345678'))
})

test('forme de l\'instantané = clés de l\'exemple du contrat', () => {
  noterRequete({ methode: 'GET', url: '/a/', statut: 200 })
  noterErreur({ genre: 'script', message: 'boum' })
  const s = instantaneDiagnostic()
  assert.deepEqual(Object.keys(s).sort(), Object.keys(EXEMPLE).sort())
  assert.deepEqual(Object.keys(s.requetes[0]).sort(), Object.keys(EXEMPLE.requetes[0]).sort())
  assert.deepEqual(Object.keys(s.erreurs[0]).sort(), Object.keys(EXEMPLE.erreurs[0]).sort())
  assert.equal(typeof s.version, 'string')
  assert.equal(typeof s.en_ligne, 'boolean')
  assert.ok(['Chrome', 'Firefox', 'Safari', 'Edge', 'autre'].includes(s.navigateur))
})

test('il_y_a_s calculé à l\'instant de l\'instantané', () => {
  const reel = Date.now
  try {
    Date.now = () => 1_000_000
    noterRequete({ methode: 'GET', url: '/a/', statut: 200 })
    noterErreur({ genre: 'script', message: 'x' })
    Date.now = () => 1_042_000
    const s = instantaneDiagnostic()
    assert.equal(s.requetes[0].il_y_a_s, 42)
    assert.equal(s.erreurs[0].il_y_a_s, 42)
  } finally {
    Date.now = reel
  }
})

test('navigateur : famille seulement, jamais l\'agent utilisateur', () => {
  const desc = Object.getOwnPropertyDescriptor(globalThis, 'navigator')
  try {
    Object.defineProperty(globalThis, 'navigator', {
      configurable: true,
      value: { userAgent: 'Mozilla/5.0 (X11) AppleWebKit/537.36 Chrome/120.0 Safari/537.36 Edg/120.0', onLine: false },
    })
    const s = instantaneDiagnostic()
    assert.equal(s.navigateur, 'Edge')
    assert.equal(s.en_ligne, false)
    assert.ok(!JSON.stringify(s).includes('Mozilla'))
  } finally {
    if (desc) Object.defineProperty(globalThis, 'navigator', desc)
    else delete globalThis.navigator
  }
})

test('aucune écriture dans le stockage du navigateur', () => {
  const ecritures = []
  const faux = {
    setItem: (...a) => ecritures.push(a), getItem: () => null, removeItem: () => {}, clear: () => {},
  }
  const avant = { l: globalThis.localStorage, s: globalThis.sessionStorage, i: globalThis.indexedDB }
  Object.defineProperty(globalThis, 'localStorage', { configurable: true, value: faux })
  Object.defineProperty(globalThis, 'sessionStorage', { configurable: true, value: faux })
  try {
    noterRequete({ methode: 'GET', url: '/a/', statut: 200 })
    noterErreur({ genre: 'script', message: 'x' })
    instantaneDiagnostic()
    viderTampon()
    assert.deepEqual(ecritures, [])
  } finally {
    for (const [k, v] of [['localStorage', avant.l], ['sessionStorage', avant.s]]) {
      if (v === undefined) delete globalThis[k]
      else Object.defineProperty(globalThis, k, { configurable: true, value: v })
    }
  }
  const src = readFileSync(join(HERE, 'tamponDiagnostic.js'), 'utf8')
  assert.ok(!/localStorage|sessionStorage|indexedDB|document\.cookie/.test(src.replace(/\/\/.*$/gm, '')))
})
