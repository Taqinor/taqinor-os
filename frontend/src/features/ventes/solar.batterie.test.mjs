// ORDRE FONDATEUR (18/08) — modèle d'économies « avec batterie » ADDITIF.
//
//   sans batterie : autoconsommé = 60 % × production
//   avec batterie : autoconsommé = 60 % × production + capacité_kWh × 1 cycle/jour
//   plafonds      : jamais plus que la production ; jamais plus que la
//                   consommation réelle quand elle est connue.
//
// Le forfait « 85 % avec batterie » ne survit QUE comme repli documenté
// (capacité inconnue). Ce fichier est le VERROU DE DÉRIVE avec son jumeau
// Python backend/django_core/apps/ventes/tests/test_battery_autoconso.py :
// mêmes entrées, mêmes valeurs attendues, DÉRIVÉES À LA MAIN des deux côtés.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  batteryKwhFromLines, PRODUCTIBLE_NET_FACTOR, SYSTEM_LOSS_TOTAL,
} from './solar.js'
import { twoBillsSavings } from './calc/tarifs.js'

// ── Fixture MIROIR (identique côté Python) ───────────────────────────────────
// 10 kWc à Casablanca : productible stocké 1651 (PVGIS, déjà net de 14 %)
// ramené aux 20 % de pertes TOTALES du fondateur → 1651 × 0,9302 = 1 535,81,
// soit 15 358 kWh/an pour 10 kWc. Batterie 10 kWh ; conso réelle 15 000 kWh/an ;
// barème ONEE.
const PROD = 15358
const BATTERY = 10
const CONSO = 15000

test('RGEN5 economieAvecNette : déduction unique, jamais hors niveau 3', async () => {
  const { economieAvecNette } = await import('./quote/economieAvecNette.js')
  const r = { roundtrip: 0.9 }
  assert.deepEqual(economieAvecNette(10000, 500, 0.5, { ...r, nette: true }),
    { economie: 9500, factureAvec: 1000, partStockee: 0 })
  assert.deepEqual(economieAvecNette(10000, null, 0.5, { ...r, nette: true }),
    { economie: 9500, factureAvec: null, partStockee: 0 })
  // Hors niveau 3, part nulle ou économie nulle : tout passe tel quel.
  assert.deepEqual(economieAvecNette(10000, 500, 0.5, r), { economie: 10000, factureAvec: 500, partStockee: 0.5 })
  assert.deepEqual(economieAvecNette(10000, 500, 0, { ...r, nette: true }), { economie: 10000, factureAvec: 500, partStockee: 0 })
  assert.deepEqual(economieAvecNette(0, 500, 0.5, { ...r, nette: true }), { economie: 0, factureAvec: 500, partStockee: 0.5 })
  const serie = [6000, 4000]
  const detail = [{ eco_avec: 6000 }, { eco_avec: 4000 }]
  economieAvecNette(10000, 500, 0.5, { ...r, nette: true,
    series: [{ valeurs: serie }, { valeurs: detail, cle: 'eco_avec' }] })
  assert.deepEqual(serie, [5700, 3800])
  assert.deepEqual(detail.map(d => d.eco_avec), [5700, 3800])
})

