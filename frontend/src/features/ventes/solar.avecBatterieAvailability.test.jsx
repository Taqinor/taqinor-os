// BAT-DIFF (fondateur, 17/09/2026) — miroir écran de
// `apps.ventes.utils.options.familles_servables` : l'option « avec » est
// servable avec un onduleur hybride + batterie, OU un hybride FACE à un
// onduleur réseau (batterie différée). Un hybride seul reste indisponible.
import { describe, expect, it } from 'vitest'
import { avecBatterieAvailability } from './solar.js'

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
    expect(r.reason).toBe('aucune batterie dans la liste')
  })

  it('réseau seul : indisponible, raison « aucun onduleur hybride »', () => {
    const r = avecBatterieAvailability([
      { designation: 'Onduleur réseau Huawei 10kW', quantite: '1' },
    ], PRODUITS, 10)
    expect(r.available).toBe(false)
    expect(r.reason).toBe('aucun onduleur hybride dans la liste')
  })
})
