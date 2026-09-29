// COUV-HOR (décision fondateur, 29/09/2026) — le balayage de dimensionnement
// industriel/commercial du devis auto recevait une consommation = factures ÷
// 1,20 MAD/kWh dès que le lead n'avait pas de distributeur (tous les leads C&I
// de la prod : le SRM n'est déduit de la ville que côté serveur). Décision :
// la CONSOMMATION suit le barème national ; le MODÈLE d'économie (`utility`)
// reste celui d'avant (mesuré : 0 devis C&I sur 61 ne change).
//
// Exécute le VRAI createAutoQuote ; seul `optimalKwcByPayback` est espionné.
import { describe, it, expect, vi, beforeEach } from 'vitest'

vi.mock('./store/ventesSlice', () => ({
  createDevis: vi.fn(() => ({ type: 'test/createDevis' })),
  addLigneDevis: vi.fn(() => ({ type: 'test/addLigneDevis' })),
}))
vi.mock('../../api/ventesApi', () => ({ default: {} }))
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
import { optimalKwcByPayback, consoAnnuelleDepuisFactures, estimerMois } from './solar'

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
