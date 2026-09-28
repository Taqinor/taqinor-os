// ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER — le total TTC de l'écran est celui que
// le noyau FACTURE (`apps/ventes/selectors.py` `_canonical_totaux` : HT brut →
// remise globale → TVA par taux → TTC, au centime), calculé sur les lignes
// telles que l'écran les persiste (prix HT = `htFromTtc`, 2 décimales).
//
// Cas dérivé à la main (chaîne serveur) :
//   Panneau 13 × 1 000 TTC @10 % → HT 909,09 → 11 818,17
//   Structure 1 × 1 000 TTC @20 % → HT 833,33 →    833,33
//   HT brut 12 651,50 ; remise 5 % = 632,575 → 632,58 ; HT net 12 018,92
//   paniers nets : 11 818,17 × 0,95 = 11 227,26 ; 833,33 × 0,95 = 791,66
//   TVA 1 122,73 + 158,33 = 1 281,06 → TTC 13 299,98
//   sans remise : TVA 1 181,82 + 166,67 → TTC 13 999,99
// Observé avant le correctif : 13 300,00 (remisé) et 14 000 (brut) — la somme
// des TTC saisis, remisée ensuite.
import { describe, expect, it } from 'vitest'
import { optionTotalsTTC, totauxCanoniquesTtc } from './solar.js'

const LIGNES = [
  { designation: 'Panneau solaire 710W', quantite: '13', prix_unit_ttc: '1000', taux_tva: 10, variante: '' },
  { designation: 'Structures aluminium', quantite: '1', prix_unit_ttc: '1000', taux_tva: 20, variante: '' },
]

describe('optionTotalsTTC — chaîne canonique (ERR-QAH-SOLAR-TOTALS-ROUNDING-ORDER)', () => {
  it('remise appliquée sur le HT brut, taux par taux, avant la TVA', () => {
    const t = optionTotalsTTC(LIGNES, '5')
    expect(t.totalSans).toBe(13299.98)
    expect(t.totalAvec).toBe(13299.98)
  })

  it('le brut est la même chaîne à 0 %', () => {
    const t = optionTotalsTTC(LIGNES, 0)
    expect(t.totalSansBrut).toBe(13999.99)
    expect(t.totalSans).toBe(13999.99)
  })

  it('mono-taux : TVA sur le HT net unique', () => {
    // 3 × 1 200 TTC @20 % → HT 1 000 ; remise 12,5 % → HT net 2 625 ; TVA 525.
    expect(totauxCanoniquesTtc([
      { quantite: '3', prix_unit_ttc: '1200', taux_tva: 20 },
    ], '12.5')).toBe(3150)
  })

  it('aucune ligne : zéro', () => {
    expect(totauxCanoniquesTtc([], 10)).toBe(0)
  })
})
