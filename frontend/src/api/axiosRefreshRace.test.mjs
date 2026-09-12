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
