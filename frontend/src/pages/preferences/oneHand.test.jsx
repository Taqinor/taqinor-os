// NTMOB22 — mode « une main » : persistance + attribut CSS, rien d'autre.
import { describe, it, expect, beforeEach, vi } from 'vitest'
import {
  getOneHandPref, setOneHandPref, applyOneHand, initPreferences,
} from './prefs'

vi.mock('../../ui/file-utils', () => ({ compressImage: vi.fn(async (f) => f) }))

describe('NTMOB22 — mode une main', () => {
  beforeEach(() => {
    localStorage.clear()
    document.documentElement.removeAttribute('data-one-hand')
  })

  it('est désactivé par défaut (aucun attribut posé)', () => {
    expect(getOneHandPref()).toBe(false)
    initPreferences()
    expect(document.documentElement.hasAttribute('data-one-hand')).toBe(false)
  })

  it('pose l\'attribut à l\'activation et le retire à la désactivation', () => {
    setOneHandPref(true)
    expect(getOneHandPref()).toBe(true)
    expect(document.documentElement.getAttribute('data-one-hand')).toBe('true')
    setOneHandPref(false)
    expect(getOneHandPref()).toBe(false)
    expect(document.documentElement.hasAttribute('data-one-hand')).toBe(false)
  })

  it('survit au rechargement (initPreferences ré-applique)', () => {
    setOneHandPref(true)
    applyOneHand(false)
    initPreferences()
    expect(document.documentElement.getAttribute('data-one-hand')).toBe('true')
  })
})
