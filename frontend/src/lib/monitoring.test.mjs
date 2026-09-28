// VX72 — Sentry frontend no-op DSN-gaté (miroir de core/monitoring.py côté
// backend). Sans VITE_SENTRY_DSN (le cas ici, plain Node sans Vite —
// import.meta.env est undefined) : no-op total, jamais d'exception, jamais
// d'import de @sentry/react (la garde DSN sort avant l'import dynamique).
// Exécuté en CI : node --test src/lib/monitoring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'

import {
  sentryDsn, isMonitoringEnabled, initMonitoring, captureException, bindCompany,
  suivreSocieteDuStore,
} from './monitoring.js'

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
