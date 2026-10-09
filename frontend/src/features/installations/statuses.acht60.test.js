import { describe, it, expect } from 'vitest'
import { canMoveStatus } from './statuses'

// ACHT60 — rester sur place n'est pas un mouvement ; un clôturé peut encore
// être ciblé vers « Réceptionné » (le serveur exige alors le motif de
// réouverture, saisi à l'écran).
describe('canMoveStatus — ACHT60', () => {
  it('canMoveStatus(x, x) est faux', () => {
    for (const s of ['signe', 'planifie', 'installe', 'receptionne', 'cloture']) {
      expect(canMoveStatus(s, s)).toBe(false)
    }
  })

  it('un seul pas avant/arrière reste permis', () => {
    expect(canMoveStatus('installe', 'receptionne')).toBe(true)
    expect(canMoveStatus('cloture', 'receptionne')).toBe(true)
    expect(canMoveStatus('signe', 'planifie')).toBe(false)
  })
})
