// ERR-QAH-FIG-EDITION-PU-TTC-ARRONDI — rouvrir un devis (`?edit=`) ne change
// ni son total ni ses prix : le TTC unitaire d'un prix PERSISTÉ est gardé au
// centime (`ttcExactFromHt`), et `htFromTtc` retrouve le HT d'origine.
// Run : node --test src/features/ventes/solar.editionPrixExact.test.mjs
import { test } from 'node:test'
import assert from 'node:assert/strict'
import { readFileSync } from 'node:fs'
import { fileURLToPath } from 'node:url'
import { dirname, join } from 'node:path'
import {
  ttcExactFromHt, ttcFromHt, htFromTtc, totauxCanoniquesTtc,
} from './solar.js'

test('aller-retour HT → TTC centime → HT : identique pour tout prix à 2 décimales', () => {
  for (const taux of [10, 14, 20]) {
    for (let c = 1; c < 400000; c += 997) {
      const ht = (c / 100).toFixed(2)
      assert.equal(htFromTtc(ttcExactFromHt(ht, taux), taux), ht, `${ht} @ ${taux} %`)
    }
  }
})

test("le total rouvert égale le total du devis (l'arrondi au dirham le décalait)", () => {
  // HT persistés dont le TTC n'est pas entier, en quantité.
  const persistees = [
    { ht: '312.49', qte: 14, taux: 10 },
    { ht: '1041.25', qte: 1, taux: 20 },
    { ht: '87.30', qte: 40, taux: 20 },
  ]
  const attendu = totauxCanoniquesTtc(persistees.map(l => ({
    quantite: l.qte, taux_tva: l.taux,
    prix_unit_ttc: (Number(l.ht) * (1 + l.taux / 100)).toFixed(6),
  })))
  const rouvert = (conv) => totauxCanoniquesTtc(persistees.map(l => ({
    quantite: String(l.qte), taux_tva: String(l.taux),
    prix_unit_ttc: String(conv(l.ht, l.taux)),
  })))
  assert.equal(rouvert(ttcExactFromHt), attendu)
  // Témoin : l'ancienne conversion au dirham décale le total.
  assert.notEqual(rouvert(ttcFromHt), attendu)
})

test('le mappeur ?edit= reconvertit au centime, jamais au dirham', () => {
  const HERE = dirname(fileURLToPath(import.meta.url))
  const SRC = readFileSync(join(HERE, '../../pages/ventes/DevisGenerator.jsx'), 'utf8')
  assert.match(SRC, /prix_unit_ttc: String\(ttcExactFromHt\(l\.prix_unitaire \|\| 0, l\.taux_tva \?\? d\.taux_tva\)\)/)
  assert.doesNotMatch(SRC, /ttcFromHt\(l\.prix_unitaire \|\| 0/)
})
