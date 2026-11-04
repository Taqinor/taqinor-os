// Course pré-auth → post-auth du refresh 401 (e2e auth.setup, run CI
// 34698649953 du 12/09/2026) : un 401 PRÉ-connexion (les providers globaux de
// /login tirent des endpoints authentifiés) déclenche un POST /token/refresh/ ;
// l'utilisateur se connecte PENDANT qu'il est en vol ; l'échec 401 du refresh
// retombe APRÈS le login réussi — les gardes du bridge passent alors (plus sur
// /login, session active) et la session NEUVE était « expirée » à tort.
// Contrat : les DEUX clients (axios.js, iaApi.js) figent l'état de session
// AVANT le refresh et, si une session est APPARUE pendant le vol, REJOUENT la
// requête au lieu d'appeler emitSessionExpired().
// Verified against SOURCE (no node_modules in worktree lanes — axios.js pulle
// ../lib/toast → sonner/React, inexécutable seul) :
//   node --test src/api/axiosRefreshRace.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'

import { estPanneDeRefresh, reprendreApresPanne } from './refreshCoordinator.js'

const HERE = dirname(fileURLToPath(import.meta.url))
const CLIENTS = {
  'axios.js': readFileSync(join(HERE, 'axios.js'), 'utf8'),
  'iaApi.js': readFileSync(join(HERE, 'iaApi.js'), 'utf8'),
}

for (const [nom, src] of Object.entries(CLIENTS)) {
  test(`${nom} : fige l'état de session AVANT le refresh 401`, () => {
    assert.match(src, /const sessionAvantRefresh = sessionEstActive\(\)/)
    // Le gel précède l'appel au refresh partagé.
    const gelIdx = src.indexOf('const sessionAvantRefresh')
    const refreshIdx = src.indexOf('await refreshSession(ORIGIN)')
    assert.ok(gelIdx !== -1 && refreshIdx !== -1 && gelIdx < refreshIdx)
  })

  test(`${nom} : une session APPARUE pendant le refresh rejoue au lieu d'expirer`, () => {
    assert.match(src, /if \(!sessionAvantRefresh && sessionEstActive\(\)\)/)
    // La garde de rejeu précède emitSessionExpired() : le monde d'avant ne
    // tue jamais la session naissante.
    const gardeIdx = src.indexOf('!sessionAvantRefresh && sessionEstActive()')
    const emitIdx = src.indexOf('emitSessionExpired()')
    assert.ok(gardeIdx !== -1 && emitIdx !== -1 && gardeIdx < emitIdx)
  })

  test(`${nom} : importe sessionEstActive depuis le bridge (source vivante, jamais une copie)`, () => {
    assert.match(src, /import \{ emitSessionExpired, sessionEstActive \} from '\.\.\/providers\/session-bridge'/)
  })
}

// ── ERR-JPB-REFRESH-MUET-SESSION-EXPIREE ────────────────────────────────────
// Un refresh qui échoue pour une raison RÉSEAU (502 de déploiement, coupure,
// délai) n'est pas une session expirée : la modale « reconnectez-vous » ne
// s'ouvre que sur un vrai refus (401/403), et la panne laisse une ligne.

for (const [nom, src] of Object.entries(CLIENTS)) {
  test(`${nom} : une panne du refresh journalise et reprend AVANT toute expiration`, () => {
    const prise = src.indexOf('catch (errRefresh)')
    assert.notEqual(prise, -1)
    assert.match(src, /estPanneDeRefresh\(errRefresh\)/)
    assert.match(src, /signalerErreurRequete\(errRefresh, \{ sessionEstActive \}\)/)
    assert.match(src, /return reprendreApresPanne\(ORIGIN, \{/)
    assert.ok(prise < src.indexOf('emitSessionExpired()'))
  })
}

test('refreshSession() borne le refresh par un délai (axios brut : aucun délai hérité)', () => {
  const source = readFileSync(join(HERE, 'refreshCoordinator.js'), 'utf8')
  assert.match(source, /withCredentials: true, timeout: DELAI_REFRESH_MS/)
})

test('estPanneDeRefresh() : réseau, délai, 5xx et 429 sont des pannes ; 401/403/400 un vrai refus', () => {
  for (const err of [
    { code: 'ERR_NETWORK' },
    { code: 'ECONNABORTED' },
    { response: { status: 502 } },
    { response: { status: 503 } },
    { response: { status: 429 } },
  ]) assert.equal(estPanneDeRefresh(err), true, JSON.stringify(err))
  for (const statut of [400, 401, 403]) {
    assert.equal(estPanneDeRefresh({ response: { status: statut } }), false, String(statut))
  }
})

function bancReprise(resultatRefresh) {
  const banc = { pauses: [], rejeux: 0, expirations: 0, signalements: [] }
  banc.options = {
    rafraichir: resultatRefresh,
    attendre: (ms) => { banc.pauses.push(ms); return Promise.resolve() },
    rejouer: () => { banc.rejeux += 1; return Promise.resolve('reponse') },
    expirer: () => { banc.expirations += 1 },
    signaler: (e) => { banc.signalements.push(e) },
  }
  return banc
}

test('reprendreApresPanne() : réseau revenu → la requête est rejouée, aucune modale', async () => {
  const banc = bancReprise(() => Promise.resolve())
  assert.equal(await reprendreApresPanne('', banc.options), 'reponse')
  assert.equal(banc.pauses.length, 1)
  assert.equal(banc.rejeux, 1)
  assert.equal(banc.expirations, 0)
  assert.equal(banc.signalements.length, 0)
})

test('reprendreApresPanne() : panne persistante → signalée et rejetée, JAMAIS une expiration', async () => {
  const panne = { code: 'ERR_NETWORK' }
  const banc = bancReprise(() => Promise.reject(panne))
  await assert.rejects(reprendreApresPanne('', banc.options), (e) => e === panne)
  assert.equal(banc.expirations, 0)
  assert.equal(banc.rejeux, 0)
  assert.deepEqual(banc.signalements, [panne])
})

test('reprendreApresPanne() : au réessai un vrai 401 → la modale reste', async () => {
  const refus = { response: { status: 401 } }
  const banc = bancReprise(() => Promise.reject(refus))
  await assert.rejects(reprendreApresPanne('', banc.options), (e) => e === refus)
  assert.equal(banc.expirations, 1)
  assert.equal(banc.signalements.length, 0)
})
