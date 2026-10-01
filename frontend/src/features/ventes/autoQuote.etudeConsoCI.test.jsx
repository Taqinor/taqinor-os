// QJR665 (décision fondateur 01/10 — barème national pour les deux) : sans
// kWh saisis, la consommation de l'ÉTUDE C&I imprimée (taux, économies,
// payback) est celle du BALAYAGE qui a choisi le kWc (parametresBalayageCI,
// barème national COUV-HOR), jamais moyenne des factures ÷ 1,75 MAD/kWh.
// Une consommation saisie reste prioritaire.
//
// Exécute le VRAI createAutoQuote ; le balayage et l'étude sont espionnés
// (passe-plat vers l'original pour l'étude) et la composition est figée.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const api = vi.hoisted(() => ({
  createDevisAtomic: vi.fn(() => Promise.resolve({ data: { id: 665 } })),
  creerDevisAuto: vi.fn(),
}))
vi.mock('../../api/ventesApi', () => ({ default: api }))

vi.mock('./solar', async (importOriginal) => {
  const original = await importOriginal()
  const ligne = (produit, designation, quantite, ttc) => ({
    produit: String(produit), designation, quantite: String(quantite),
    prix_unit_ttc: ttc, taux_tva: 20,
  })
  return {
    ...original,
    optimalKwcByPayback: vi.fn(() => ({ nbPanneaux: 40 })),
    autoFillLines: vi.fn((_produits, opts) => [
      ligne(10, 'Panneau 710W', opts.nbPanneaux, 1100),
      ligne(11, 'Onduleur réseau 30 kW', 1, 30000),
    ]),
    computeEtudeIndustrielle: vi.fn((args) => original.computeEtudeIndustrielle(args)),
  }
})

import { createAutoQuote, consoMensuelleEtudeCI, parametresBalayageCI } from './autoQuote'
import {
  optimalKwcByPayback, computeEtudeIndustrielle, consoAnnuelleDepuisFactures,
  estimerMois, KWH_PRICE,
} from './solar'

beforeEach(() => { vi.clearAllMocks() })

async function creer(lead) {
  const id = await createAutoQuote({ lead, produits: [], discountStr: '0' })
  expect(id).toBe(665)
  expect(optimalKwcByPayback).toHaveBeenCalledTimes(1)
  expect(computeEtudeIndustrielle).toHaveBeenCalledTimes(1)
  return {
    balayage: optimalKwcByPayback.mock.calls[0][0],
    etude: computeEtudeIndustrielle.mock.calls[0][0],
  }
}

describe('QJR665 — étude C&I : même consommation que le balayage', () => {
  it.each(['commercial', 'industriel'])(
    'lead %s avec factures sans kWh : conso de l’étude × 12 == conso du balayage',
    async (type) => {
      const { balayage, etude } = await creer({
        id: 1, type_installation: type, facture_hiver: '4000', distributeur: null,
      })
      expect(balayage.consoAnnuelleKwh)
        .toBe(consoAnnuelleDepuisFactures(estimerMois(4000, 4000), 'onee'))
      expect(etude.consoMensuelleKwh * 12).toBeCloseTo(balayage.consoAnnuelleKwh, 6)
      // Plus jamais la moyenne des factures ÷ 1,75 MAD/kWh.
      expect(etude.consoMensuelleKwh).not.toBe(Math.round(4000 / KWH_PRICE))
      // La conso imprimée par l'étude est celle du balayage.
      const corps = api.createDevisAtomic.mock.calls[0][0]
      expect(corps.mode_installation).toBe(type)
    })

  it('été différent : les deux suivent les mêmes 12 factures', async () => {
    const { balayage, etude } = await creer({
      id: 2, type_installation: 'commercial', facture_hiver: '4000',
      ete_differente: true, facture_ete: '6000',
    })
    expect(etude.consoMensuelleKwh * 12).toBeCloseTo(balayage.consoAnnuelleKwh, 6)
  })

  it('une conso saisie reste prioritaire pour l’étude', async () => {
    const { etude } = await creer({
      id: 3, type_installation: 'industriel', facture_hiver: '4000',
      conso_mensuelle_kwh: '12345',
    })
    expect(etude.consoMensuelleKwh).toBe(12345)
  })
})

// L'Édition complète (DevisGenerator) lit la MÊME fonction sur les factures
// affichées : exécutée ici telle quelle.
describe('QJR665 — consoMensuelleEtudeCI (partagée avec l’Édition complète)', () => {
  const factures = estimerMois(5200, 3900)
  it.each([undefined, 'onee', 'lydec', 'srm_casablanca_settat'])(
    'distributeur %s : conso mensuelle == conso du balayage ÷ 12', (distributeurDeclare) => {
      const attendu = parametresBalayageCI({ factures, mode: 'commercial', distributeurDeclare })
        .consoAnnuelleKwh / 12
      expect(attendu).toBeGreaterThan(0)
      expect(consoMensuelleEtudeCI({ factures, mode: 'commercial', distributeurDeclare }))
        .toBe(attendu)
    })
  it('aucune facture : 0 (jamais un chiffre inventé)', () => {
    expect(consoMensuelleEtudeCI({ factures: [], mode: 'industriel' })).toBe(0)
    expect(consoMensuelleEtudeCI({})).toBe(0)
  })
})
