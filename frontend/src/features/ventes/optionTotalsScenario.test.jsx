// ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION — le total « avec batterie » du
// formulaire de création est CELUI que le serveur persiste.
//
// Constat (qa-explorer 2026-09-28) : sur un devis « Les deux (Sans + Avec) »
// de 13 lignes SANS `variante` (onduleur réseau Huawei + onduleur hybride Deye
// + batteries + Smart Meter + clé Wi-Fi), le formulaire affichait 97 391 alors
// que le noyau (`utils/options.py` `deux_options_declarees` →
// `filter_lines_for_option`) persistait 94 391,16 : le serveur applique QF9
// (accessoires Huawei retirés du panier servi par un onduleur non-Huawei) dès
// que l'alternative est DÉCLARÉE par le scénario, l'écran ne l'appliquait
// qu'aux lignes variantées. Écart = Smart Meter 1 800 + clé Wi-Fi 1 200.
//
// Les attentes ci-dessous sont dérivées à la main des lignes (et identiques à
// celles de `apps/ventes/tests/test_err_qah_total_divergence_creation.py`).
import { describe, expect, it } from 'vitest'
import { optionTotalsTTC } from './solar.js'

const L = (designation, quantite, prix_unit_ttc, taux_tva = 20) =>
  ({ designation, quantite: String(quantite), prix_unit_ttc: String(prix_unit_ttc), taux_tva, variante: '' })

const COMPOSITION = [
  L('Panneau solaire 710W', 13, 1100, 10),
  L('Onduleur réseau Huawei 10kW', 1, 19800),
  L('Onduleur hybride Deye 10kW', 1, 27600),
  L('Batterie Dyness 5 kWh', 2, 13800),
  L('Smart Meter', 1, 1800),
  L('Wifi Dongle', 1, 1200),
  L('Structures aluminium', 13, 840),
  L('Socles', 26, 72),
  L('Câble solaire Nexans 6 mm² (au mètre)', 60, 14.4),
  L('Câble de terre Nexans 6 mm² (au mètre)', 40, 14.4),
  L('Tableau De Protection AC/DC', 1, 1800),
  L('Installation', 1, 4800),
  L('Transport', 1, 960),
]

describe('optionTotalsTTC — scénario déclaré (ERR-QAH-VENTES-TOTAL-DIVERGENCE-CREATION)', () => {
  it('« Les deux » : le panier AVEC perd les accessoires Huawei, comme le noyau', () => {
    const t = optionTotalsTTC(COMPOSITION, 0, { scenario: 'Les deux (Sans + Avec)' })
    // Observé avant le correctif : 94 292 (Smart Meter + clé Wi-Fi comptés).
    expect(t.totalAvec).toBe(91292)
    expect(t.totalSans).toBe(58892)
  })

  it('scénario mono « Avec batterie » : même panier que le noyau', () => {
    const t = optionTotalsTTC(COMPOSITION, 0, { scenario: 'Avec batterie' })
    expect(t.totalAvec).toBe(91292)
  })

  it('sans scénario (appelants historiques) : comportement inchangé', () => {
    const t = optionTotalsTTC(COMPOSITION, 0)
    expect(t.totalAvec).toBe(94292)
  })

  it('équipement non servable en deux options (pas de réseau) : aucune règle QF9', () => {
    const sansReseau = COMPOSITION.filter(l => !/réseau/.test(l.designation))
    const t = optionTotalsTTC(sansReseau, 0, { scenario: 'Les deux (Sans + Avec)' })
    expect(t.totalAvec).toBe(94292)
  })
})
