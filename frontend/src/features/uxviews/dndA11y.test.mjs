// NTUX21 — reorderIds : logique PURE du glisser-déposer d'une liste à plat
// (favoris, vues personnelles), testée sans simuler de vrais événements
// pointeur @dnd-kit (non fiable en jsdom — même bar de test que
// `pages/home/HomeMenu.jsx`, qui ne simule pas non plus de vrai glisser).
import { describe, it, expect } from 'vitest'
import { reorderIds, buildDndListAnnouncements } from './dndA11y'

describe('reorderIds (NTUX21)', () => {
  it('déplace un élément à la position déposée', () => {
    const next = reorderIds([1, 2, 3, 4], { active: { id: 1 }, over: { id: 3 } })
    expect(next).toEqual([2, 3, 1, 4])
  })

  it('renvoie null quand il n’y a pas de cible de dépôt', () => {
    expect(reorderIds([1, 2, 3], { active: { id: 1 }, over: null })).toBeNull()
  })

  it('renvoie null quand la cible EST l’élément déplacé (aucun mouvement)', () => {
    expect(reorderIds([1, 2, 3], { active: { id: 2 }, over: { id: 2 } })).toBeNull()
  })

  it('déplace vers le début de la liste', () => {
    const next = reorderIds([1, 2, 3], { active: { id: 3 }, over: { id: 1 } })
    expect(next).toEqual([3, 1, 2])
  })
})

describe('buildDndListAnnouncements (NTUX21)', () => {
  it('annonce le début du déplacement avec le libellé résolu', () => {
    const announcements = buildDndListAnnouncements((id) => `Élément ${id}`)
    expect(announcements.onDragStart({ active: { id: 1 } }))
      .toBe('Déplacement de Élément 1 commencé.')
  })

  it('annonce l’absence de cible valide', () => {
    const announcements = buildDndListAnnouncements((id) => `Élément ${id}`)
    expect(announcements.onDragOver({ active: { id: 1 }, over: null }))
      .toBe("Élément 1 n'est au-dessus d'aucune position valide.")
  })
})
