import { describe, it, expect } from 'vitest'
import {
  selectModulesDesactives,
  isModuleDisabled,
  filterNavSections,
} from './moduleGating'

describe('ODX6 — moduleGating (gating par module actif/désactivé)', () => {
  it('selectModulesDesactives : repli [] si absent', () => {
    expect(selectModulesDesactives({ auth: {} })).toEqual([])
    expect(selectModulesDesactives({ auth: { modulesDesactives: ['flotte'] } }))
      .toEqual(['flotte'])
  })

  it('isModuleDisabled : clé désactivée → true ; clé absente/nulle → false', () => {
    expect(isModuleDisabled(['flotte'], 'flotte')).toBe(true)
    expect(isModuleDisabled(['flotte'], 'stock')).toBe(false)
    // Section globale sans clé : jamais désactivée.
    expect(isModuleDisabled(['flotte'], null)).toBe(false)
    expect(isModuleDisabled(['flotte'], undefined)).toBe(false)
    expect(isModuleDisabled([], 'flotte')).toBe(false)
  })

  it('filterNavSections : liste vide de désactivés → sections INCHANGÉES (même référence)', () => {
    const sections = [{ key: 'stock' }, { label: 'ADMIN' }]
    // Chemin par défaut : aucune copie, byte-identique.
    expect(filterNavSections(sections, [])).toBe(sections)
    expect(filterNavSections(sections, undefined)).toBe(sections)
  })

  it('filterNavSections : retire la section du module désactivé, garde les autres et les globales', () => {
    const sections = [
      { label: null },                 // globale (Dashboard) sans clé
      { key: 'stock', label: 'STOCK' },
      { key: 'flotte', label: 'FLOTTE' },
      { label: 'ADMINISTRATION' },     // globale sans clé
    ]
    const out = filterNavSections(sections, ['flotte'])
    expect(out.map((s) => s.label)).toEqual([null, 'STOCK', 'ADMINISTRATION'])
    // La section flotte est bien absente.
    expect(out.find((s) => s.key === 'flotte')).toBeUndefined()
  })
})
