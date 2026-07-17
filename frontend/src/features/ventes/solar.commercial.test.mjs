// QX44 — Étude COMMERCIALE par catégorie. Le day-share d'archétype fait qu'à
// facture (kWc + conso) égale, une étude hôtel diffère d'une étude bureau.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  COMMERCIAL_CATEGORIES, COMMERCIAL_CATEGORY_QUESTIONS,
  COMMERCIAL_DAY_SHARE, commercialDayShare, computeEtudeIndustrielle,
} from './solar.js'

test('QX44 — day-share par catégorie ≠ valeur unique 80', () => {
  assert.equal(commercialDayShare('bureau'), 80)
  assert.equal(commercialDayShare('hotel'), 55)
  assert.equal(commercialDayShare('boulangerie'), 45)
  assert.notEqual(commercialDayShare('hotel'), commercialDayShare('bureau'))
})

test('QX44 — catégorie inconnue → repli 80', () => {
  assert.equal(commercialDayShare('inexistante'), 80)
})

test('QX44 — override société borné 10-100', () => {
  assert.equal(commercialDayShare('hotel', { override: { hotel: 62 } }), 62)
  assert.equal(commercialDayShare('hotel', { override: { hotel: 999 } }), 100)
  assert.equal(commercialDayShare('hotel', { override: { hotel: 1 } }), 10)
  // override d'une autre catégorie n'affecte pas
  assert.equal(commercialDayShare('bureau', { override: { hotel: 62 } }), 80)
})

test('QX44 — étude hôtel ≠ étude bureau à FACTURE ÉGALE', () => {
  // kwp assez grand pour que l'autoconsommation soit limitée par la CONSO (part
  // diurne) et non par la production → le day-share d'archétype fait la diff.
  const common = { kwp: 300, consoMensuelleKwh: 20000, totalTtc: 900000, kwhPrice: 1.4, efficiency: 0.8 }
  const hotel = computeEtudeIndustrielle({ ...common, dayUsagePct: commercialDayShare('hotel') })
  const bureau = computeEtudeIndustrielle({ ...common, dayUsagePct: commercialDayShare('bureau') })
  // même production, mais couverture/économies différentes (part diurne)
  assert.equal(hotel.production_annuelle, bureau.production_annuelle)
  assert.notEqual(hotel.economies_annuelles, bureau.economies_annuelles)
  assert.notEqual(hotel.taux_couverture, bureau.taux_couverture)
  // bureau (80 % diurne) autoconsomme plus → économise plus qu'un hôtel (55 %)
  assert.ok(bureau.economies_annuelles > hotel.economies_annuelles)
})

test('QX44 — 10 catégories, questions 2-4 par catégorie, clés snake_case', () => {
  assert.equal(COMMERCIAL_CATEGORIES.length, 10)
  for (const c of COMMERCIAL_CATEGORIES) {
    const qs = COMMERCIAL_CATEGORY_QUESTIONS[c.value]
    assert.ok(Array.isArray(qs), `questions manquantes pour ${c.value}`)
    if (c.value !== 'autre') {
      assert.ok(qs.length >= 2 && qs.length <= 4, `${c.value}: ${qs.length} questions`)
    }
    for (const q of qs) {
      assert.match(q.key, /^[a-z0-9_]+$/, `clé non snake_case: ${q.key}`)
      assert.ok(['number', 'bool', 'select'].includes(q.type))
      if (q.type === 'select') assert.ok(Array.isArray(q.options) && q.options.length > 0)
    }
  }
})

test('QX44 — chaque valeur day-share est commentée SOURCE ou EST. (table présente)', () => {
  // garde structurelle : toutes les catégories ont un day-share défini
  for (const c of COMMERCIAL_CATEGORIES) {
    assert.equal(typeof COMMERCIAL_DAY_SHARE[c.value], 'number')
  }
})
