// Revue chantier 26/10/2026 — « Comparer » apparie avant/après par SUJET de
// créneau (toiture_avant ↔ toiture_apres), libellé du créneau sur la paire ;
// l'ordre d'ajout ne sert plus qu'au reste (photos sans créneau).
import { describe, it, expect } from 'vitest'
import { apparierAvantApres } from './apparierPhotos'

const photo = (id, slotCle, slotLibelle) => ({ id, url: `/p/${id}`, slotCle, slotLibelle })

describe('apparierAvantApres', () => {
  it('apparie par créneau même si l’ordre diffère, puis par ordre', () => {
    const avant = [
      photo(1, 'tableau_electrique_avant', 'Tableau électrique (avant)'),
      photo(2, 'toiture_avant', 'Toiture avant pose'),
      photo(3),
    ]
    const apres = [
      photo(10, 'toiture_apres', 'Toiture après pose'),
      photo(11),
      photo(12, 'tableau_electrique_apres', 'Tableau électrique (après)'),
    ]
    const { pairs, surplusAvant, surplusApres } = apparierAvantApres(avant, apres)
    expect(pairs.map((p) => [p.before.id, p.after.id])).toEqual([[1, 12], [2, 10], [3, 11]])
    expect(pairs[1].label).toBe('Toiture avant pose → Toiture après pose')
    expect(pairs[2].label).toBeNull()
    expect(surplusAvant).toEqual([])
    expect(surplusApres).toEqual([])
  })

  it('jamais de paire inventée : le surplus reste à part', () => {
    const { pairs, surplusAvant } = apparierAvantApres(
      [photo(1, 'toiture_avant', 'Toiture avant pose'), photo(2)], [])
    expect(pairs).toEqual([])
    expect(surplusAvant.map((p) => p.id)).toEqual([1, 2])
  })
})
