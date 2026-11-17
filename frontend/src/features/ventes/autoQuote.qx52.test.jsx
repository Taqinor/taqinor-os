import { describe, it, expect } from 'vitest'
import { LEAD_TYPE_TO_MODE, libelleSuccesDevisAuto } from './autoQuote'
import { DAY_USAGE_DEFAULTS } from './solar'

// QX52 — parité mode↔type sur 4 modes (frontend). Aucun mode ne tombe dans le
// libellé/comportement d'un autre : commercial route vers SON mode (plus le
// repli historique vers industriel).

describe('QX52 — LEAD_TYPE_TO_MODE (4 modes cohérents)', () => {
  it('commercial route désormais vers commercial (plus industriel)', () => {
    expect(LEAD_TYPE_TO_MODE.commercial).toBe('commercial')
  })

  it('chaque type de lead route vers son propre mode', () => {
    expect(LEAD_TYPE_TO_MODE.residentiel).toBe('residentiel')
    expect(LEAD_TYPE_TO_MODE.industriel).toBe('industriel')
    expect(LEAD_TYPE_TO_MODE.agricole).toBe('agricole')
  })

  it('commercial et industriel restent DISTINCTS', () => {
    expect(LEAD_TYPE_TO_MODE.commercial).not.toBe(LEAD_TYPE_TO_MODE.industriel)
  })

  it('aucune valeur cible n’est hors des 4 modes canoniques', () => {
    const valid = new Set(['residentiel', 'commercial', 'industriel', 'agricole'])
    for (const v of Object.values(LEAD_TYPE_TO_MODE)) {
      expect(valid.has(v)).toBe(true)
    }
  })
})

describe('CIQ128 — plus de part diurne C&I d’écran', () => {
  it('DAY_USAGE_DEFAULTS ne porte plus d’entrée commerciale ni industrielle', () => {
    expect(DAY_USAGE_DEFAULTS).not.toHaveProperty('Commerciale')
    expect(DAY_USAGE_DEFAULTS).not.toHaveProperty('Industrielle')
    expect(typeof DAY_USAGE_DEFAULTS['Résidentielle']).toBe('number')
  })
})

// D 17/11/2026 — le bandeau de succès dit aussi l'option AVEC batterie.
describe('libelleSuccesDevisAuto — option avec batterie', () => {
  const normaliser = (t) => t.replace(/[\u202f\u00a0]/g, ' ')
  const base = { reference: 'DEV-1', kwc: 5, total_ttc: 41000, economie_an_1_ht: 12000, retour_ans: 4.2 }
  it('sans les clés « avec » : la phrase historique, inchangée', () => {
    expect(normaliser(libelleSuccesDevisAuto(base)))
      .toBe('DEV-1 · 5 kWc · 41 000 MAD TTC · économie ≈ 12 000 MAD/an · retour ≈ 4,2 ans')
    expect(libelleSuccesDevisAuto({ ...base, economie_an_1_ht_avec: null, retour_ans_avec: null }))
      .toBe(libelleSuccesDevisAuto(base))
  })
  it('avec les clés « avec » : les deux options sont libellées', () => {
    const t = normaliser(libelleSuccesDevisAuto({
      ...base, economie_an_1_ht_avec: 15000, retour_ans_avec: 6.1, kwc_avec: 6,
    }))
    expect(t).toContain('sans batterie : économie ≈ 12 000 MAD/an · retour ≈ 4,2 ans')
    expect(t).toContain('avec batterie : économie ≈ 15 000 MAD/an · retour ≈ 6,1 ans')
  })
})
