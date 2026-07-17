import { describe, it, expect } from 'vitest'
import {
  monthlyWaterDemand,
  cropKcMonthly,
  annualWaterFromMonthly,
  datePalmCitedPerTree,
  CROP_CITED,
  CROP_STAGES,
  ET0_MONTHLY,
  RAIN_EFF_MONTHLY,
} from './agronomy'
import {
  pumpHydraulicKwMin,
  pumpSufficiencyWarning,
  CV_TO_KW,
} from './solar'

// QX48 — moteur agronomique v2 (série mensuelle FAO-56). Les valeurs CANONIQUES
// ci-dessous sont partagées avec le test Python de parité
// (apps/ventes/tests/test_qx48_agronomy_v2.py) : tout écart révèle un miroir
// désaligné.

describe('monthlyWaterDemand — série mensuelle', () => {
  it('12 valeurs mensuelles + intégrale annuelle', () => {
    const r = monthlyWaterDemand({ crop: 'agrumes', region: 'souss-massa', surfaceHa: 2, method: 'goutte' })
    expect(r.kc).toHaveLength(12)
    expect(r.etcMmDay).toHaveLength(12)
    expect(r.grossM3HaMonth).toHaveLength(12)
    expect(r.grossM3FarmDay).toHaveLength(12)
    // le pic d'été dépasse le creux d'hiver
    expect(r.grossM3FarmDay[6]).toBeGreaterThan(r.grossM3FarmDay[0])
    expect(r.annualGrossM3Ha).toBeGreaterThan(0)
  })

  it('culture inconnue → Kc plat 0.85 (jamais d’exception)', () => {
    expect(() => monthlyWaterDemand({})).not.toThrow()
    expect(cropKcMonthly('zzz').slice(0, 3)).toEqual([0.85, 0.85, 0.85])
  })

  it('la technique d’irrigation change le brut (gravitaire > goutte)', () => {
    const base = { crop: 'agrumes', region: 'souss-massa', surfaceHa: 2 }
    const goutte = monthlyWaterDemand({ ...base, method: 'goutte' })
    const grav = monthlyWaterDemand({ ...base, method: 'gravitaire' })
    expect(grav.annualGrossM3Ha).toBeGreaterThan(goutte.annualGrossM3Ha)
  })
})

describe('QX48 — 3 valeurs Maroc CITÉES (calage recherche 2026-07-16)', () => {
  it('avocatier Gharb goutte : ~10 084 m³/ha/an, dans la bande citée 8-12 000', () => {
    const r = monthlyWaterDemand({ crop: 'avocatier', region: 'gharb-loukkos', surfaceHa: 1, method: 'goutte' })
    expect(r.annualGrossM3Ha).toBe(10084)
    const [lo, hi] = CROP_CITED.avocatier.annual_m3_ha
    expect(r.annualGrossM3Ha).toBeGreaterThanOrEqual(lo)
    expect(r.annualGrossM3Ha).toBeLessThanOrEqual(hi)
  })

  it('myrtille Gharb goutte : pic ~75.8 m³/ha/j, proche des ~80 cités', () => {
    const r = monthlyWaterDemand({ crop: 'myrtille', region: 'gharb-loukkos', surfaceHa: 1, method: 'goutte' })
    expect(r.peakM3HaDay).toBe(75.8)
    expect(r.peakM3HaDay).toBeGreaterThanOrEqual(60)
    expect(r.peakM3HaDay).toBeLessThanOrEqual(100)
  })

  it('dattier : 51 m³/arbre/an est une valeur citée stockée + sourcée', () => {
    expect(datePalmCitedPerTree()).toBe(51)
    expect(CROP_CITED.dattier.source).toMatch(/2026-07-16/)
    expect(CROP_CITED.dattier.trees_per_ha).toBe(100)
  })
})

describe('cropKcMonthly — stades FAO-56 → série mensuelle (vecteurs canoniques)', () => {
  it('amandier (déciduous) : dormance hiver, Kc-mid été', () => {
    expect(cropKcMonthly('amandier')).toEqual(
      [0, 0, 0.4, 0.65, 0.9, 0.9, 0.9, 0.9, 0.9, 0.817, 0.733, 0])
  })
  it('céréales (cycle hiver MA)', () => {
    expect(cropKcMonthly('cereales')).toEqual(
      [0.9, 1.15, 1.15, 0.775, 0, 0, 0, 0, 0, 0, 0.4, 0.65])
  })
  it('évergreen (avocatier) : Kc constant toute l’année', () => {
    expect(cropKcMonthly('avocatier')).toEqual(new Array(12).fill(0.85))
  })
})

describe('annualWaterFromMonthly — intégrale (remplace 0.62×300)', () => {
  it('somme des besoins journaliers × jours du mois', () => {
    const r = monthlyWaterDemand({ crop: 'avocatier', region: 'gharb-loukkos', surfaceHa: 1, method: 'goutte' })
    expect(annualWaterFromMonthly(r)).toBe(10082)
  })
  it('entrée invalide → 0 (jamais d’exception)', () => {
    expect(annualWaterFromMonthly(null)).toBe(0)
    expect(annualWaterFromMonthly({})).toBe(0)
  })
})

describe('sources : chaque constante estimée est flaggée', () => {
  it('régions/pluie présentes pour gharb-loukkos + haouz (nouvelles)', () => {
    expect(ET0_MONTHLY['gharb-loukkos']).toHaveLength(12)
    expect(ET0_MONTHLY.haouz).toHaveLength(12)
    expect(RAIN_EFF_MONTHLY['gharb-loukkos']).toHaveLength(12)
  })
  it('cannabis licite est marqué estimé (flag ANRAC)', () => {
    expect(CROP_STAGES.cannabis.kcEstimated).toBe(true)
  })
  it('la table couvre ~16+ cultures', () => {
    expect(Object.keys(CROP_STAGES).length).toBeGreaterThanOrEqual(16)
  })
})

describe('QX48(f) — garde de suffisance hydraulique (repli CV, jamais bloquant)', () => {
  it('kW_min = Q·H·2,725/(1000·η)', () => {
    // 15 m³/h × 60 m × 2.725 / (1000 × 0.5) = 4.905 → 4.91
    expect(pumpHydraulicKwMin(15, 60, 0.5)).toBe(4.91)
    expect(pumpHydraulicKwMin(15, 60)).toBe(4.91) // η défaut 0.5
  })
  it('avertit quand la pompe saisie est sous le minimum', () => {
    const cvKw = Math.round(3 * CV_TO_KW * 100) / 100 // 3 CV ≈ 2.21 kW < 4.905
    const w = pumpSufficiencyWarning({ hmt: 60, debit: 15, cvKw })
    expect(w).toMatch(/sous-dimensionnée/)
    expect(w).toMatch(/4\.9 kW/)
  })
  it('pas d’avertissement quand la pompe suffit', () => {
    const cvKw = Math.round(8 * CV_TO_KW * 100) / 100 // 8 CV ≈ 5.88 kW > 4.905
    expect(pumpSufficiencyWarning({ hmt: 60, debit: 15, cvKw })).toBeNull()
  })
  it('entrées invalides → null (jamais bloquant)', () => {
    expect(pumpHydraulicKwMin(0, 60)).toBeNull()
    expect(pumpHydraulicKwMin(15, 0)).toBeNull()
    expect(pumpSufficiencyWarning({})).toBeNull()
    expect(pumpSufficiencyWarning({ hmt: 60, debit: 15, cvKw: 0 })).toBeNull()
  })
})
