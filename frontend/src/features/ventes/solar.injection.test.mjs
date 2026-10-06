// QX50 — Injection 82-21 (miroir de quote_engine/constants_82_21.py). Valeurs
// canoniques IDENTIQUES au test Python (test_qx50_injection_82_21.py) : parité.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  INJECTION_82_21, netTarif8221,
} from './solar.js'

test('QX50 — tarif net (rachat − frais réseau)', () => {
  assert.equal(Math.round(netTarif8221() * 10000) / 10000, 0.0555)      // hors pointe
  assert.equal(Math.round(netTarif8221(true) * 10000) / 10000, 0.0855)  // pointe
  assert.ok(netTarif8221() >= 0)
})

test('QX50 — constantes sourcées présentes', () => {
  assert.equal(INJECTION_82_21.PLAFOND_PCT, 20)
  assert.match(INJECTION_82_21.MENTION, /ANRE 03\/2026-02\/2027/)
  assert.match(INJECTION_82_21.MENTION, /plafond en révision/)
})
