// BAT-DIFF (fondateur, 17/09/2026) — miroir écran de
// `apps.ventes.utils.options.familles_servables` : l'option « avec » est
// servable avec un onduleur hybride + batterie, OU un hybride FACE à un
// onduleur réseau (batterie différée). Un hybride seul reste indisponible.
import { describe, expect, it } from 'vitest'
import { avecBatterieAvailability } from './calc/totaux.js'

const PRODUITS = [{ nom: 'Onduleur hybride Deye 10kW' }]

describe('avecBatterieAvailability', () => {
  it('hybride + batterie : disponible, batterie non différée', () => {
    const r = avecBatterieAvailability([
      { designation: 'Onduleur hybride Deye 10kW', quantite: '1' },
      { designation: 'Batterie Dyness 10 kWh', quantite: '1' },
    ], PRODUITS, 10)
    expect(r).toEqual({ available: true, batterieDifferee: false })
  })

  it('hybride face au réseau, batterie à 0 : disponible, batterie différée', () => {
    const r = avecBatterieAvailability([
      { designation: 'Onduleur réseau Huawei 10kW', quantite: '1' },
      { designation: 'Onduleur hybride Deye 10kW', quantite: '1' },
      { designation: 'Batterie Dyness 10 kWh', quantite: '0' },
    ], PRODUITS, 10)
    expect(r).toEqual({ available: true, batterieDifferee: true })
  })

  it('hybride seul, sans batterie : indisponible (Z1)', () => {
    const r = avecBatterieAvailability([
      { designation: 'Onduleur hybride Deye 10kW', quantite: '1' },
    ], PRODUITS, 10)
    expect(r.available).toBe(false)
    expect(r.reason).toBe('aucune batterie dans les lignes du devis — ajoutez-en une')
  })

  it('réseau seul : indisponible, raison « aucun onduleur hybride »', () => {
    const r = avecBatterieAvailability([
      { designation: 'Onduleur réseau Huawei 10kW', quantite: '1' },
    ], PRODUITS, 10)
    expect(r.available).toBe(false)
    expect(r.reason).toBe('aucun onduleur hybride dans les lignes du devis — cliquez « Auto-remplir » ou ajoutez-en un')
  })
})

// Fondateur 24/11/2026 — fiche « DEYE SUN-80K-SG02HP3-EU-EM6 » : rôle déclaré
// hybride, 80 kW sur la fiche, mais un nom qui ne dit ni « onduleur hybride »
// ni « 80 kW ». L'écran continuait d'annoncer « onduleurs hybrides de 30 kW ».
describe('avecBatterieAvailability — rôle déclaré et fiche avant le nom', () => {
  const DEYE_30 = { id: 127, nom: 'Onduleur hybride Deye 30kW Triphasé', role_devis_effectif: 'onduleur_hybride' }
  const DEYE_80 = {
    id: 229, nom: 'DEYE SUN-80K-SG02HP3-EU-EM6', role_devis_effectif: 'onduleur_hybride',
    specs_solaire: { famille: 'onduleur', ac_kw: 80 },
  }
  const RESEAU = [{ designation: 'Onduleur réseau Huawei 150kW Triphasé', quantite: '3' }]

  it('le plus gros hybride du catalogue est lu sur son rôle et sa fiche', () => {
    const sans80 = avecBatterieAvailability(RESEAU, [DEYE_30], 605.6)
    expect(sans80.reason).toContain('il faudrait 21 onduleurs hybrides de 30 kW')
    const avec80 = avecBatterieAvailability(RESEAU, [DEYE_30, DEYE_80], 605.6)
    expect(avec80.reason).toBe('aucun onduleur hybride dans les lignes du devis — cliquez « Auto-remplir » ou ajoutez-en un')
    expect(avecBatterieAvailability(RESEAU, [DEYE_30, DEYE_80], 700).reason)
      .toContain('il faudrait 9 onduleurs hybrides de 80 kW')
  })

  it('une ligne posée à la main sur ce produit compte comme un hybride', () => {
    const lignes = [
      { produit: 229, designation: 'DEYE SUN-80K-SG02HP3-EU-EM6', quantite: '8', role_devis: '' },
      { designation: 'Batterie Deye BOS-B Pro haute tension — 16 kWh', quantite: '4' },
    ]
    expect(avecBatterieAvailability(lignes, [DEYE_80], 605.6)).toEqual({ available: true, batterieDifferee: false })
    // Sans produit lié ni rôle : le nom tranche, comme avant.
    expect(avecBatterieAvailability([{ designation: 'DEYE SUN-80K-SG02HP3-EU-EM6', quantite: '8' }], [DEYE_80], 605.6)
      .available).toBe(false)
  })

  it("commercial / industriel : jamais le conseil d'ajouter un produit au catalogue", () => {
    const r = avecBatterieAvailability(RESEAU, [DEYE_30], 605.6, { ci: true })
    expect(r.available).toBe(false)
    expect(r.reason).toContain("c'est le calcul qui compose l'option « avec batterie »")
    expect(r.reason).not.toContain('ajoutez au catalogue')
  })
})
