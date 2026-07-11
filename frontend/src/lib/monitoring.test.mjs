// VX72 — Sentry frontend no-op DSN-gaté (miroir de core/monitoring.py côté
// backend). Sans VITE_SENTRY_DSN (le cas ici, plain Node sans Vite —
// import.meta.env est undefined) : no-op total, jamais d'exception, jamais
// d'import de @sentry/react (paquet non installé dans ce dépôt — comme
// sentry-sdk absent de requirements.txt côté backend).
// Exécuté en CI : node --test src/lib/monitoring.test.mjs
import test from 'node:test'
import assert from 'node:assert/strict'

import { sentryDsn, isMonitoringEnabled, initMonitoring, captureException } from './monitoring.js'

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
