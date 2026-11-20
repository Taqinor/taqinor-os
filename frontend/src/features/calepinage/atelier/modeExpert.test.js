import { describe, it, expect } from 'vitest'
import { cleModeExpert, lireModeExpert, ecrireModeExpert } from './modeExpert'

/* ACAL394 — le « mode expert » est mémorisé PAR UTILISATEUR, dans CE navigateur. */
function stockageEnMemoire() {
  const m = new Map()
  return { getItem: (k) => (m.has(k) ? m.get(k) : null), setItem: (k, v) => m.set(k, String(v)) }
}

describe('ACAL394 — mode expert par utilisateur', () => {
  it('écrit pour l’utilisateur 7 : relu expert pour 7, guidé pour 8', () => {
    const s = stockageEnMemoire()
    expect(lireModeExpert(7, s)).toBe(false)
    ecrireModeExpert(7, true, s)
    expect(lireModeExpert(7, s)).toBe(true)
    expect(lireModeExpert(8, s)).toBe(false)
  })

  it('la clé porte l’identifiant de l’utilisateur', () => {
    expect(cleModeExpert(7)).toBe('calepinage.mode_expert.7')
    expect(cleModeExpert(7)).not.toBe(cleModeExpert(8))
  })

  it('décocher revient en guidé', () => {
    const s = stockageEnMemoire()
    ecrireModeExpert(7, true, s)
    ecrireModeExpert(7, false, s)
    expect(lireModeExpert(7, s)).toBe(false)
  })

  it('un stockage qui lève laisse le guidé, sans erreur', () => {
    const casse = { getItem() { throw new Error('refusé') }, setItem() { throw new Error('refusé') } }
    expect(lireModeExpert(7, casse)).toBe(false)
    expect(() => ecrireModeExpert(7, true, casse)).not.toThrow()
  })
})
