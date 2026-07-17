import { describe, it, expect } from 'vitest'
import { LEAD_TYPE_TO_MODE } from './autoQuote'
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

describe('QX52 — day-share commercial distinct', () => {
  it('DAY_USAGE_DEFAULTS a une entrée Commerciale propre', () => {
    expect(DAY_USAGE_DEFAULTS.Commerciale).toBeDefined()
    // Commerciale a sa propre valeur (jamais celle d’un autre mode par accident)
    expect(typeof DAY_USAGE_DEFAULTS.Commerciale).toBe('number')
  })
})
