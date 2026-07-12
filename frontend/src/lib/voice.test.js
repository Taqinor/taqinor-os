import { describe, it, expect } from 'vitest'
import { voice, VOICE_MOMENTS } from './voice'

/* VX156 — contrat de la voix : les 6 moments à forte charge portent chacun une
   chaîne NON VIDE (pas de moment muet ni de placeholder oublié). */
describe('VX156 — voix Taqinor', () => {
  it('expose exactement les 6 moments', () => {
    expect(VOICE_MOMENTS).toHaveLength(6)
  })

  it('chaque moment porte une (des) chaîne(s) non vide(s)', () => {
    for (const key of VOICE_MOMENTS) {
      const v = voice[key]
      expect(v, `moment manquant : ${key}`).toBeDefined()
      const strings = typeof v === 'string' ? [v] : Object.values(v)
      for (const s of strings) {
        expect(typeof s).toBe('string')
        expect(s.trim().length, `chaîne vide dans ${key}`).toBeGreaterThan(0)
      }
    }
  })
})
