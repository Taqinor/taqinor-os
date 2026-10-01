// COUV-HOR (décision fondateur, 29/09/2026) — le balayage de dimensionnement
// industriel/commercial du devis auto recevait une consommation = factures ÷
// 1,20 MAD/kWh dès que le lead n'avait pas de distributeur (tous les leads C&I
// de la prod : le SRM n'est déduit de la ville que côté serveur). Décision :
// la CONSOMMATION suit le barème national ; le MODÈLE d'économie (`utility`)
// reste celui d'avant (mesuré : 0 devis C&I sur 61 ne change).
//
// Exécute le VRAI createAutoQuote ; seul `optimalKwcByPayback` est espionné.
import { describe, it, expect, vi, beforeEach } from 'vitest'

// QJR543 — la création passe par ventesApi.createDevisAtomic (jamais atteinte
// ici : le balayage ne retient aucun palier et le devis s'arrête sur son refus).
vi.mock('../../api/ventesApi', () => ({ default: { createDevisAtomic: vi.fn() } }))
vi.mock('./solar', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    // Aucun palier retenu : le devis s'arrête sur son refus explicite, après
    // que le balayage a reçu ses arguments — les seuls que ce test lit.
    optimalKwcByPayback: vi.fn(() => ({ nbPanneaux: 0 })),
  }
})

import { createAutoQuote } from './autoQuote'
import {
  optimalKwcByPayback, consoAnnuelleDepuisFactures, estimerMois, productibleForCity,
} from './solar'

async function argumentsDuBalayage(lead) {
  try {
    await createAutoQuote({ lead, produits: [], discountStr: '0', dispatch: vi.fn() })
  } catch { /* refus explicite « aucune taille » : attendu ici */ }
  expect(optimalKwcByPayback).toHaveBeenCalledTimes(1)
  return optimalKwcByPayback.mock.calls[0][0]
}

const FACTURES = estimerMois(4000, 4000)
const CONSO_NATIONALE = consoAnnuelleDepuisFactures(FACTURES, 'onee')

beforeEach(() => { vi.clearAllMocks() })

describe('COUV-HOR — balayage C&I : conso au barème national, modèle inchangé', () => {
  it('lead SANS distributeur : conso nationale (jamais 48 000 ÷ 1,20 = 40 000), modèle estimation conservé', async () => {
    const args = await argumentsDuBalayage({
      id: 42, type_installation: 'commercial', facture_hiver: '4000', distributeur: null,
    })
    expect(args.consoAnnuelleKwh).toBe(CONSO_NATIONALE)
    expect(args.consoAnnuelleKwh).not.toBe(40000)
    expect(args.utility).toBeUndefined()
  })

  it('lead SRM : même conso nationale, modèle inchangé', async () => {
    const args = await argumentsDuBalayage({
      id: 43, type_installation: 'industriel', facture_hiver: '4000',
      distributeur: 'srm_casablanca_settat',
    })
    expect(args.consoAnnuelleKwh).toBe(CONSO_NATIONALE)
    expect(args.utility).toBeUndefined()
  })

  it('lead ONEE : inchangé (conso et modèle par tranches)', async () => {
    const args = await argumentsDuBalayage({
      id: 44, type_installation: 'commercial', facture_hiver: '4000', distributeur: 'onee',
    })
    expect(args.consoAnnuelleKwh).toBe(CONSO_NATIONALE)
    expect(args.utility).toBe('onee')
  })
})

// ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — le balayage du devis auto chiffre la
// production au productible de la VILLE du lead (comme l'aperçu et le PDF),
// jamais au repli historique GHI × 0,8 de `computeROI`.
describe('ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — balayage du devis auto', () => {
  it("lead d'Agadir : le balayage reçoit le productible d'Agadir", async () => {
    expect(productibleForCity('Agadir')).not.toBe(productibleForCity(''))
    const args = await argumentsDuBalayage({
      id: 45, type_installation: 'commercial', facture_hiver: '4000',
      distributeur: 'onee', ville: 'Agadir',
    })
    expect(args.productible).toBe(productibleForCity('Agadir'))
  })

  it('lead sans ville : le productible par défaut, jamais absent', async () => {
    const args = await argumentsDuBalayage({
      id: 46, type_installation: 'industriel', facture_hiver: '4000', distributeur: 'onee',
    })
    expect(args.productible).toBe(productibleForCity(''))
  })
})
