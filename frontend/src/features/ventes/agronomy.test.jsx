import { describe, it, expect } from 'vitest'
import {
  waterDemandFromFarm,
  requiredFlow,
  hectaresIrrigable,
  annualWater,
  KC_MID,
  ET0_PEAK_MM_J,
  IRRIGATION_EFFICIENCY,
} from './agronomy'

describe('waterDemandFromFarm', () => {
  it('exemple travaillé : 2 ha agrumes Souss-Massa goutte', () => {
    const r = waterDemandFromFarm({
      crop: 'agrumes', region: 'souss-massa', surfaceHa: 2, method: 'goutte',
    })
    // ET0 7.5 × Kc 0.65 = 4.875 mm/j
    expect(r.etcPeakMm).toBeCloseTo(4.875, 3)
    // net 48.75 m³/ha/j ÷ 0.90 ≈ 54.17 m³/ha/j
    expect(r.grossM3HaDay).toBeCloseTo(54.2, 1)
    // × 2 ha ≈ 108 m³/jour
    expect(r.m3DayPeak).toBeGreaterThanOrEqual(107)
    expect(r.m3DayPeak).toBeLessThanOrEqual(109)
    expect(r.inputs.kc).toBe(KC_MID.agrumes)
    expect(r.inputs.et0).toBe(ET0_PEAK_MM_J['souss-massa'])
  })

  it('la technique d’irrigation change le résultat (gravitaire > goutte)', () => {
    const base = { crop: 'agrumes', region: 'souss-massa', surfaceHa: 2 }
    const goutte = waterDemandFromFarm({ ...base, method: 'goutte' })
    const gravitaire = waterDemandFromFarm({ ...base, method: 'gravitaire' })
    expect(gravitaire.m3DayPeak).toBeGreaterThan(goutte.m3DayPeak)
    expect(gravitaire.grossM3HaDay).toBeGreaterThan(goutte.grossM3HaDay)
    expect(IRRIGATION_EFFICIENCY.gravitaire).toBeLessThan(IRRIGATION_EFFICIENCY.goutte)
  })

  it('exploitation 100 % cheptel (sans surface) donne un m3DayPeak positif', () => {
    const r = waterDemandFromFarm({ livestock: { vache_laitiere: 20, mouton: 100 } })
    expect(r).not.toBeNull()
    // 20 × 150 + 100 × 12 = 4200 L = 4.2 m³/j
    expect(r.livestockM3Day).toBeCloseTo(4.2, 1)
    expect(r.cropM3Day).toBe(0)
    expect(r.m3DayPeak).toBeGreaterThan(0)
  })

  it('cultures + cheptel s’additionnent', () => {
    const cropsOnly = waterDemandFromFarm({
      crop: 'maraichage', region: 'tadla', surfaceHa: 1, method: 'goutte',
    })
    const both = waterDemandFromFarm({
      crop: 'maraichage', region: 'tadla', surfaceHa: 1, method: 'goutte',
      livestock: { vache_laitiere: 10 },
    })
    expect(both.m3DayPeak).toBeGreaterThan(cropsOnly.m3DayPeak)
  })

  it('culture / région inconnues retombent sur les valeurs par défaut', () => {
    const r = waterDemandFromFarm({
      crop: 'inconnue', region: 'mars', surfaceHa: 1, method: 'magie',
    })
    expect(r.etcPeakMm).toBeCloseTo(6.375, 3)
    expect(r.inputs.kc).toBe(0.85)
    expect(r.inputs.efficiency).toBe(0.75)
  })
})

describe('requiredFlow', () => {
  it('108 m³/jour sur 7 h ≈ 15.4 m³/h', () => {
    expect(requiredFlow(108, 7)).toBeCloseTo(15.4, 1)
  })
  it('heures nulles ou négatives → null', () => {
    expect(requiredFlow(108, 0)).toBeNull()
    expect(requiredFlow(108, -3)).toBeNull()
  })
})

describe('hectaresIrrigable', () => {
  it('renvoie un nombre positif sensé', () => {
    expect(hectaresIrrigable(20000, 'agrumes')).toBeCloseTo(2, 1)
    expect(hectaresIrrigable(20000, 'agrumes')).toBeGreaterThan(0)
  })
  it('culture inconnue → consommation par défaut', () => {
    expect(hectaresIrrigable(8000, 'xxx')).toBeCloseTo(1, 1)
  })
})

describe('annualWater', () => {
  it('ramène le jour de pointe à un volume annuel', () => {
    expect(annualWater(108)).toBe(Math.round(108 * 0.62 * 300))
    expect(annualWater(108)).toBeGreaterThan(0)
  })
  it('jours invalides → 0', () => {
    expect(annualWater(108, 0)).toBe(0)
  })
})

describe('entrées invalides (défensif, ne lève jamais)', () => {
  it('objet vide → null', () => {
    expect(() => waterDemandFromFarm({})).not.toThrow()
    expect(waterDemandFromFarm({})).toBeNull()
  })
  it('aucun argument → null', () => {
    expect(() => waterDemandFromFarm()).not.toThrow()
    expect(waterDemandFromFarm()).toBeNull()
  })
  it('valeurs absurdes ne lèvent pas', () => {
    expect(() => requiredFlow('abc', 'def')).not.toThrow()
    expect(() => hectaresIrrigable(null, null)).not.toThrow()
    expect(() => annualWater(undefined)).not.toThrow()
    expect(annualWater(undefined)).toBe(0)
  })
})
