import { describe, it, expect, afterEach } from 'vitest'
import { act, renderHook } from '@testing-library/react'
import { cleModeExpert, lireModeExpert, ecrireModeExpert, useModeExpert } from './modeExpert'

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

/* Le pont vers les scripts de l'atelier (ACAL552, 584, 717) : ils lisent
   `document.body.dataset.modeExpert === '1'`. */
describe('mode expert — data-mode-expert sur document.body', () => {
  afterEach(() => {
    try { localStorage.clear() } catch { /* stockage indisponible */ }
    delete document.body.dataset.modeExpert
  })

  it('guidé : aucun attribut ; basculer en expert le pose, revenir le retire', () => {
    const { result } = renderHook(() => useModeExpert(false))
    expect(document.body.dataset.modeExpert).toBeUndefined()
    act(() => result.current[1](true))
    expect(document.body.getAttribute('data-mode-expert')).toBe('1')
    act(() => result.current[1](false))
    expect(document.body.dataset.modeExpert).toBeUndefined()
  })

  it('?mode=expert le pose ; le démontage de l’atelier le retire', () => {
    const { unmount } = renderHook(() => useModeExpert(true))
    expect(document.body.dataset.modeExpert).toBe('1')
    unmount()
    expect(document.body.dataset.modeExpert).toBeUndefined()
  })
})

describe('ACAL1438 — le mode est partagé entre composants', () => {
  afterEach(() => {
    try { localStorage.clear() } catch { /* stockage indisponible */ }
    delete document.body.dataset.modeExpert
  })

  it('deux composants montés : basculer dans l’un met l’autre à jour, sans recharger', () => {
    const a = renderHook(() => useModeExpert(false))
    const b = renderHook(() => useModeExpert(false))
    expect(a.result.current[0]).toBe(false)
    expect(b.result.current[0]).toBe(false)
    act(() => a.result.current[1](true))
    expect(b.result.current[0]).toBe(true)
    expect(a.result.current[0]).toBe(true)
    act(() => b.result.current[1](false))
    expect(a.result.current[0]).toBe(false)
  })

  it('le démontage d’un composant ne retire pas le pont tant qu’un autre tient le mode', () => {
    const a = renderHook(() => useModeExpert(false))
    const b = renderHook(() => useModeExpert(false))
    act(() => a.result.current[1](true))
    b.unmount()
    expect(document.body.dataset.modeExpert).toBe('1')
    a.unmount()
    expect(document.body.dataset.modeExpert).toBeUndefined()
  })
})
