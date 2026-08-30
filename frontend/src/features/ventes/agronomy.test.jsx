import { describe, it, expect } from 'vitest'
import {
  waterDemandFromFarm,
  requiredFlow,
  hectaresIrrigable,
  annualWater,
  IRRIGATION_EFFICIENCY,
  monthlyWaterDemand,
} from './agronomy'

// QJR166 — waterDemandFromFarm n'est plus un second moteur (ET0 de pointe fixe
// × Kc mi-saison, sans pluie créditée) : il route désormais par le moteur
// mensuel v2 (monthlyWaterDemand, QX48) et renvoie le MAXIMUM de la série —
// miroir exact de peak_need_m3_day() côté backend (agronomy.py, post-QJR152).
describe('waterDemandFromFarm — route par le moteur mensuel v2 (QJR166)', () => {
  it('le résultat EST le maximum de la série mensuelle (même appel, même valeur)', () => {
    const args = { crop: 'agrumes', region: 'souss-massa', surfaceHa: 2, method: 'goutte' }
    const r = waterDemandFromFarm(args)
    const monthly = monthlyWaterDemand(args)
    expect(r.m3DayPeak).toBe(Math.round(monthly.peakM3FarmDay))
    expect(r.peakM3HaDay).toBe(monthly.peakM3HaDay)
  })

  it('la technique d’irrigation change le résultat (gravitaire > goutte)', () => {
    const base = { crop: 'agrumes', region: 'souss-massa', surfaceHa: 2 }
    const goutte = waterDemandFromFarm({ ...base, method: 'goutte' })
    const gravitaire = waterDemandFromFarm({ ...base, method: 'gravitaire' })
    expect(gravitaire.m3DayPeak).toBeGreaterThan(goutte.m3DayPeak)
    expect(IRRIGATION_EFFICIENCY.gravitaire).toBeLessThan(IRRIGATION_EFFICIENCY.goutte)
  })

  it('culture / région inconnues ne lèvent pas (repli sur les défauts du moteur mensuel)', () => {
    const r = waterDemandFromFarm({
      crop: 'inconnue', region: 'mars', surfaceHa: 1, method: 'magie',
    })
    expect(r).not.toBeNull()
    expect(r.m3DayPeak).toBeGreaterThan(0)
  })
})

// Parité 3 cultures — valeurs v2 mesurées au fold du 30/08 (dérivées, pas
// inventées : `monthlyWaterDemand` réel sur une région/surface/méthode
// représentative de la culture — Souss-Massa = bassin agrumicole, Saïss =
// « capitale » oléicole marocaine, Drâa-Tafilalet = oasis phoenicicoles).
// Même fixture côté backend : apps/ventes/tests/test_qx48_agronomy_v2.py.
describe('waterDemandFromFarm — parité 3 cultures (QJR166)', () => {
  it('agrumes, Souss-Massa, 2 ha, goutte → 90 m³/jour (89.6 arrondi)', () => {
    const r = waterDemandFromFarm({
      crop: 'agrumes', region: 'souss-massa', surfaceHa: 2, method: 'goutte',
    })
    expect(r.m3DayPeak).toBe(90)
  })

  it('olivier, Saïss, 1.5 ha, goutte → 82 m³/jour (81.8 arrondi)', () => {
    const r = waterDemandFromFarm({
      crop: 'olivier', region: 'saiss', surfaceHa: 1.5, method: 'goutte',
    })
    expect(r.m3DayPeak).toBe(82)
  })

  it('dattier, Drâa-Tafilalet, 2.8 ha, goutte → 250 m³/jour (250.2 arrondi)', () => {
    const r = waterDemandFromFarm({
      crop: 'dattier', region: 'draa-tafilalet', surfaceHa: 2.8, method: 'goutte',
    })
    expect(r.m3DayPeak).toBe(250)
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
