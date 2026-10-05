// AGR216 — un taux de TVA 0 % saisi reste 0 % (il redevenait 20 %, car 0 est
// « faux » en JavaScript). null / '' / NaN ⇒ défaut ; 0 ⇒ 0. Aucun taux par
// défaut ne change.
import { test } from 'node:test'
import assert from 'node:assert/strict'
import {
  ttcFromHt, ttcExactFromHt, htFromTtc, tauxTvaOf, tauxTvaOuDefaut,
  totauxCanoniquesTtc, TVA_STANDARD_DEFAUT,
} from './solar.js'
import { lignesServeurVersEcran } from './quote/lignesEcran.js'

test('null / vide / NaN ⇒ défaut ; 0 ⇒ 0', () => {
  for (const v of [null, undefined, '', 'abc', NaN]) {
    assert.equal(tauxTvaOuDefaut(v), TVA_STANDARD_DEFAUT)
    assert.equal(ttcFromHt(100, v), 120)
    assert.equal(ttcExactFromHt(100, v), 120)
    assert.equal(htFromTtc(120, v), '100.00')
  }
  assert.equal(tauxTvaOuDefaut(0), 0)
  assert.equal(tauxTvaOuDefaut('0'), 0)
  assert.equal(ttcFromHt(100, 0), 100)
  assert.equal(ttcFromHt(100, '0'), 100)
  assert.equal(ttcExactFromHt(100.55, 0), 100.55)
  assert.equal(htFromTtc(100, 0), '100.00')
  assert.equal(htFromTtc(100, '0.00'), '100.00')
})

test('aller-retour TTC → HT → TTC exact à 0 %', () => {
  for (const ttc of [1, 37.5, 1234, 36873.11]) {
    const ht = htFromTtc(ttc, 0)
    assert.equal(ttcExactFromHt(ht, 0), ttc)
  }
})

test('Produit.tva = 0 ⇒ 0 ; absent/null ⇒ standard', () => {
  assert.equal(tauxTvaOf({ tva: 0 }), 0)
  assert.equal(tauxTvaOf({ tva: '0.00' }), 0)
  assert.equal(tauxTvaOf({ tva: 10 }), 10)
  assert.equal(tauxTvaOf({ tva: null }), 20)
  assert.equal(tauxTvaOf({}), 20)
  assert.equal(tauxTvaOf({ tva: null }, 18), 18)
})

test('total TTC mixte {0, 10, 20} exact au centime (HT 1000 chacun)', () => {
  const lignes = [
    { quantite: '1', prix_unit_ttc: '1000', taux_tva: '0', remise: '0' },
    { quantite: '1', prix_unit_ttc: '1100', taux_tva: '10', remise: '0' },
    { quantite: '1', prix_unit_ttc: '1200', taux_tva: '20', remise: '0' },
  ]
  // HT 1000 + 1000 + 1000 ; TVA 0 + 100 + 200 ⇒ TTC 3300 (valeur serveur).
  assert.equal(Number(totauxCanoniquesTtc(lignes)), 3300)
})

test('réouverture ?edit= : une ligne serveur à 0 % reste à 0 %', () => {
  const [l] = lignesServeurVersEcran([
    { produit: 1, designation: 'x', quantite: 1, prix_unitaire: '1000.00', taux_tva: '0.00' },
  ], 20)
  assert.equal(l.taux_tva, '0')
  assert.equal(l.prix_unit_ttc, '1000')
  const [m] = lignesServeurVersEcran([
    { produit: 1, designation: 'x', quantite: 1, prix_unitaire: '1000.00' },
  ], 20)
  assert.equal(m.taux_tva, '20')
})
