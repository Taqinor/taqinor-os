// QJR603 (D-QJR5-14, fondateur 30/09/2026) — un lead PRO « kWh seulement »
// (conso_mensuelle_kwh, sinon bill_kwh — la porte serveur devis_auto.py) est
// prêt pour le devis automatique, mais createAutoQuote ne savait dimensionner
// le C&I que depuis la facture d'hiver : bouton ouvert, puis échec « renseignez
// une facture ». Désormais ces kWh entrent dans le balayage C&I EXISTANT
// (parametresBalayageCI → optimalKwcByPayback) avec consoAnnuelleKwh =
// kWh mensuels × 12 ; les factures du balayage sont celles que le barème
// national (factureMad, inverse exact de consoAnnuelleDepuisFactures)
// associe à ces kWh — aucun coefficient inventé.
//
// Exécute le VRAI createAutoQuote ; le balayage est espionné (passe-plat vers
// l'original) et la composition est remplacée par des lignes fixes.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const api = vi.hoisted(() => ({
  createDevisAtomic: vi.fn(() => Promise.resolve({ data: { id: 777 } })),
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
    optimalKwcByPayback: vi.fn(() => ({ nbPanneaux: 140 })),
    autoFillLines: vi.fn((_produits, opts) => [
      ligne(10, 'Panneau 710W', opts.nbPanneaux, 1100),
      ligne(11, 'Onduleur réseau 100 kW', 1, 90000),
    ]),
  }
})

import { createAutoQuote } from './autoQuote'
import {
  optimalKwcByPayback, autoFillLines, factureMad, ONEE_TRANCHES,
  consoAnnuelleDepuisFactures, estimerKwcDepuisFacture,
} from './solar'

beforeEach(() => { vi.clearAllMocks() })

const KWH_MOIS = 30000
const FACTURE_MOIS = factureMad(KWH_MOIS, ONEE_TRANCHES).totalMad

describe('QJR603 — lead pro « kWh seulement » : dimensionné depuis ses kWh', () => {
  it.each([
    ['industriel', { conso_mensuelle_kwh: KWH_MOIS }],
    ['industriel', { bill_kwh: String(KWH_MOIS) }],
    ['commercial', { conso_mensuelle_kwh: String(KWH_MOIS) }],
  ])('%s %j sans facture : le devis est créé, balayé sur 360 000 kWh/an', async (type, kwh) => {
    const id = await createAutoQuote({
      lead: { id: 5, type_installation: type, facture_hiver: null, ...kwh },
      produits: [], discountStr: '0',
    })
    expect(id).toBe(777)
    expect(optimalKwcByPayback).toHaveBeenCalledTimes(1)
    const args = optimalKwcByPayback.mock.calls[0][0]
    expect(args.consoAnnuelleKwh).toBe(360000)
    // Les factures du balayage : le barème national appliqué à ces kWh.
    expect(args.factures).toEqual(Array(12).fill(FACTURE_MOIS))
    // …dont l'inverse redonne exactement la conso saisie (aucun coefficient).
    expect(consoAnnuelleDepuisFactures(args.factures)).toBe(360000)
    expect(args.besoinKwc).toBe(estimerKwcDepuisFacture(FACTURE_MOIS))
    expect(args.besoinKwc).toBeGreaterThan(0)
    // La composition reçoit le nombre de panneaux du balayage.
    expect(autoFillLines.mock.calls[0][1].nbPanneaux).toBe(140)
    const corps = api.createDevisAtomic.mock.calls[0][0]
    expect(corps.mode_installation).toBe(type)
    expect(corps.lignes[0].quantite).toBe('140')
  })

  it('lead industriel avec une facture d’hiver : le balayage reste celui de la facture (inchangé)', async () => {
    await createAutoQuote({
      lead: { id: 6, type_installation: 'industriel', facture_hiver: '4000', conso_mensuelle_kwh: KWH_MOIS },
      produits: [], discountStr: '0',
    })
    const args = optimalKwcByPayback.mock.calls[0][0]
    expect(args.besoinKwc).toBe(estimerKwcDepuisFacture(4000))
  })

  it('lead pro sans facture ni kWh : refus explicite, aucun devis', async () => {
    await expect(createAutoQuote({
      lead: { id: 7, type_installation: 'industriel', facture_hiver: null },
      produits: [], discountStr: '0',
    })).rejects.toMatchObject({ detail: expect.stringMatching(/Devis auto impossible/) })
    expect(api.createDevisAtomic).not.toHaveBeenCalled()
  })
})
