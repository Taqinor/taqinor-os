import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDelayedLoading } from './useDelayedLoading'

/* L153 — Seuils anti-scintillement du chargement différé.
   Règle : rien sous 300 ms, spinner discret entre 300 et 500 ms, squelette
   au-delà de 500 ms, et JAMAIS spinner + squelette en même temps. Horloge
   factice pour piloter les seuils à la milliseconde. */
describe('useDelayedLoading (L153)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('ne montre rien quand isLoading est faux (état idle)', () => {
    const { result } = renderHook(() => useDelayedLoading(false))
    expect(result.current.phase).toBe('idle')
    expect(result.current.showSpinner).toBe(false)
    expect(result.current.showSkeleton).toBe(false)
  })

  it('ne montre rien sous 300 ms (anti-scintillement)', () => {
    const { result } = renderHook(() => useDelayedLoading(true))
    // À t=0 : pending, rien d'affiché.
    expect(result.current.phase).toBe('pending')
    expect(result.current.showSpinner).toBe(false)
    expect(result.current.showSkeleton).toBe(false)
    // À t=299 ms : toujours rien.
    act(() => {
      vi.advanceTimersByTime(299)
    })
    expect(result.current.showSpinner).toBe(false)
    expect(result.current.showSkeleton).toBe(false)
  })

  it('montre un spinner (et pas le squelette) entre 300 et 500 ms', () => {
    const { result } = renderHook(() => useDelayedLoading(true))
    act(() => {
      vi.advanceTimersByTime(300)
    })
    expect(result.current.phase).toBe('spinner')
    expect(result.current.showSpinner).toBe(true)
    expect(result.current.showSkeleton).toBe(false)
    // Toujours spinner seul à 499 ms.
    act(() => {
      vi.advanceTimersByTime(199)
    })
    expect(result.current.showSpinner).toBe(true)
    expect(result.current.showSkeleton).toBe(false)
  })

  it('bascule sur le squelette au-delà de 500 ms et coupe le spinner', () => {
    const { result } = renderHook(() => useDelayedLoading(true))
    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(result.current.phase).toBe('skeleton')
    expect(result.current.showSkeleton).toBe(true)
    // JAMAIS spinner + squelette ensemble.
    expect(result.current.showSpinner).toBe(false)
  })

  it('ne montre jamais spinner ET squelette en même temps, à aucun instant', () => {
    const { result } = renderHook(() => useDelayedLoading(true))
    for (const ms of [0, 150, 300, 400, 500, 800, 2000]) {
      act(() => {
        vi.advanceTimersByTime(ms)
      })
      expect(result.current.showSpinner && result.current.showSkeleton).toBe(false)
    }
  })

  it('repasse à idle dès que isLoading redevient faux', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDelayedLoading(loading),
      { initialProps: { loading: true } },
    )
    act(() => {
      vi.advanceTimersByTime(500)
    })
    expect(result.current.showSkeleton).toBe(true)
    rerender({ loading: false })
    expect(result.current.phase).toBe('idle')
    expect(result.current.showSpinner).toBe(false)
    expect(result.current.showSkeleton).toBe(false)
  })

  it('un chargement rapide (< 300 ms) ne fait jamais clignoter quoi que ce soit', () => {
    const { result, rerender } = renderHook(
      ({ loading }) => useDelayedLoading(loading),
      { initialProps: { loading: true } },
    )
    act(() => {
      vi.advanceTimersByTime(200)
    })
    rerender({ loading: false })
    // Avancer au-delà des anciens seuils : aucun timer ne doit déclencher.
    act(() => {
      vi.advanceTimersByTime(1000)
    })
    expect(result.current.showSpinner).toBe(false)
    expect(result.current.showSkeleton).toBe(false)
  })

  it('honore des seuils personnalisés', () => {
    const { result } = renderHook(() =>
      useDelayedLoading(true, { spinnerDelay: 100, skeletonDelay: 250 }),
    )
    act(() => {
      vi.advanceTimersByTime(100)
    })
    expect(result.current.showSpinner).toBe(true)
    act(() => {
      vi.advanceTimersByTime(150)
    })
    expect(result.current.showSkeleton).toBe(true)
    expect(result.current.showSpinner).toBe(false)
  })
})
