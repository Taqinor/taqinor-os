// QX50 — Injection 82-21 (miroir de quote_engine/constants_82_21.py). Valeurs
// canoniques IDENTIQUES au test Python (test_qx50_injection_82_21.py) : parité.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  INJECTION_82_21, netTarif8221, injection8221, computeEtudeIndustrielle,
} from './solar.js'

test('QX50 — tarif net (rachat − frais réseau)', () => {
  assert.equal(Math.round(netTarif8221() * 10000) / 10000, 0.0555)      // hors pointe
  assert.equal(Math.round(netTarif8221(true) * 10000) / 10000, 0.0855)  // pointe
  assert.ok(netTarif8221() >= 0)
})

test('QX50 — surplus borné 20 % + valeur nette', () => {
  // prod 400000, autoconso 352000 → surplus 48000 (< plafond 80000)
  assert.deepEqual(injection8221(400000, 352000), { kwh: 48000, dh: 2664 })
  // prod 100000, autoconso 0 → BORNÉ à 20 % = 20000
  assert.deepEqual(injection8221(100000, 0), { kwh: 20000, dh: 1110 })
  // pas de surplus / surplus négatif → 0
  assert.deepEqual(injection8221(100000, 100000), { kwh: 0, dh: 0 })
  assert.deepEqual(injection8221(100000, 150000), { kwh: 0, dh: 0 })
})

test('QX50 — constantes sourcées présentes', () => {
  assert.equal(INJECTION_82_21.PLAFOND_PCT, 20)
  assert.match(INJECTION_82_21.MENTION, /ANRE 03\/2026-02\/2027/)
  assert.match(INJECTION_82_21.MENTION, /plafond en révision/)
})

test('QX50 — étude avec injection = étude sans + ligne (OFF par défaut)', () => {
  const params = {
    kwp: 300, consoMensuelleKwh: 20000, dayUsagePct: 80,
    totalTtc: 900000, kwhPrice: 1.4, efficiency: 0.8,
  }
  const sans = computeEtudeIndustrielle(params)
  const avec = computeEtudeIndustrielle({ ...params, injectionEnabled: true })
  // OFF par défaut : pas de ligne injection
  assert.equal(sans.injection_dh_an, undefined)
  assert.equal(sans.injection_82_21, undefined)
  // base d'étude IDENTIQUE (l'injection est une ligne séparée)
  assert.equal(avec.economies_annuelles, sans.economies_annuelles)
  assert.equal(avec.taux_autoconso, sans.taux_autoconso)
  assert.equal(avec.production_annuelle, sans.production_annuelle)
  // la ligne injection est présente et bornée ≥ 0
  assert.equal(avec.injection_82_21, true)
  assert.ok(avec.injection_kwh_an >= 0)
  assert.ok(avec.injection_dh_an >= 0)
  // plafond : injection ≤ 20 % de la production
  assert.ok(avec.injection_kwh_an <= avec.production_annuelle * 0.2 + 1)
})
