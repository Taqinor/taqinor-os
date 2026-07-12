import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useRotatingLabel } from './useRotatingLabel'

/* VX132 — Chargement long conscient : au moins 2 libellés honnêtes se
   succèdent toutes les ~2.5 s pendant une attente connue-longue (ex. PDF
   premium), jamais une fausse barre de progression. Horloge factice pour
   piloter la rotation à la milliseconde (même motif que useDelayedLoading). */
const LABELS = ['Mise en page des schémas…', 'Calcul du système…', 'Finalisation du document…']

describe('useRotatingLabel (VX132)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('démarre sur le premier libellé', () => {
    const { result } = renderHook(() => useRotatingLabel(LABELS))
    expect(result.current).toBe(LABELS[0])
  })

  it('fait tourner au moins 2 libellés distincts après ~2.5 s x 2', () => {
    const { result } = renderHook(() => useRotatingLabel(LABELS))
    const seen = new Set([result.current])

    act(() => { vi.advanceTimersByTime(2500) })
    seen.add(result.current)

    act(() => { vi.advanceTimersByTime(2500) })
    seen.add(result.current)

    expect(seen.size).toBeGreaterThanOrEqual(2)
  })

  it('respecte un intervalMs personnalisé', () => {
    const { result } = renderHook(() => useRotatingLabel(LABELS, { intervalMs: 1000 }))
    expect(result.current).toBe(LABELS[0])
    act(() => { vi.advanceTimersByTime(1000) })
    expect(result.current).toBe(LABELS[1])
  })

  it('active=false : ne tourne pas (rien à annoncer hors attente)', () => {
    const { result } = renderHook(() => useRotatingLabel(LABELS, { active: false }))
    act(() => { vi.advanceTimersByTime(10000) })
    expect(result.current).toBe(LABELS[0])
  })

  it('repart du premier libellé à un nouveau cycle actif', () => {
    const { result, rerender } = renderHook(
      ({ active }) => useRotatingLabel(LABELS, { active }),
      { initialProps: { active: true } },
    )
    act(() => { vi.advanceTimersByTime(2500) })
    expect(result.current).toBe(LABELS[1])

    rerender({ active: false })
    rerender({ active: true })
    expect(result.current).toBe(LABELS[0])
  })

  it('aucune fausse barre de progression : renvoie une chaîne, pas un pourcentage', () => {
    const { result } = renderHook(() => useRotatingLabel(LABELS))
    expect(typeof result.current).toBe('string')
    expect(result.current).not.toMatch(/%/)
  })
})
