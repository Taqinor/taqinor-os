import { describe, it, expect } from 'vitest'
import { canMoveStatus, canRecordMiseEnService } from './statuses'

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

// ACHT113 — règle partagée du bouton « Enregistrer la mise en service ».
describe('canRecordMiseEnService — ACHT113', () => {
  it('offert sur Installé, Réceptionné et mise_en_service hérité', () => {
    for (const statut of ['installe', 'receptionne', 'mise_en_service', 'pose']) {
      expect(canRecordMiseEnService({ statut, annule: false })).toBe(true)
    }
  })

  it('refusé avant Installé, sur Clôturé et sur annulé', () => {
    for (const statut of ['signe', 'planifie', 'en_cours', 'a_planifier', 'cloture']) {
      expect(canRecordMiseEnService({ statut })).toBe(false)
    }
    expect(canRecordMiseEnService({ statut: 'receptionne', annule: true })).toBe(false)
    expect(canRecordMiseEnService(null)).toBe(false)
  })
})
