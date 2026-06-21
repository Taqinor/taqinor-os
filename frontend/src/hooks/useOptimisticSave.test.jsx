import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useOptimisticSave } from './useOptimisticSave'

/* L151 — Sauvegarde optimiste avec rollback.
   On vérifie : l'affichage bascule tout de suite sur la valeur optimiste, le
   statut passe par 'saving' → 'saved' au succès, et au moindre échec l'ancienne
   valeur est restaurée (rollback) avec statut 'error'. L'affordance « ligne en
   cours » (opacité réduite + occupé) est aussi exposée. */
describe('useOptimisticSave (L151)', () => {
  beforeEach(() => {
    vi.useFakeTimers()
  })
  afterEach(() => {
    vi.useRealTimers()
  })

  it('démarre au repos avec la valeur serveur affichée', () => {
    const { result } = renderHook(() => useOptimisticSave('NEW'))
    expect(result.current.value).toBe('NEW')
    expect(result.current.status).toBe('idle')
    expect(result.current.isSaving).toBe(false)
    expect(result.current.statusLabel).toBe('')
  })

  it('affiche la valeur optimiste immédiatement pendant l’enregistrement', async () => {
    let resolveCommit
    const commit = vi.fn(() => new Promise((res) => { resolveCommit = res }))
    const { result } = renderHook(() => useOptimisticSave('NEW'))

    act(() => {
      result.current.save('CONTACTED', commit)
    })

    // Tout de suite : valeur optimiste + statut 'saving' + libellé FR.
    expect(result.current.value).toBe('CONTACTED')
    expect(result.current.status).toBe('saving')
    expect(result.current.isSaving).toBe(true)
    expect(result.current.statusLabel).toBe('Enregistrement…')
    expect(commit).toHaveBeenCalledTimes(1)

    await act(async () => {
      resolveCommit({})
    })
  })

  it('passe à "Enregistré" au succès, puis revient au repos après le délai', async () => {
    const commit = vi.fn(() => Promise.resolve({ ok: true }))
    const { result } = renderHook(() => useOptimisticSave('NEW', { savedDuration: 1500 }))

    await act(async () => {
      await result.current.save('CONTACTED', commit)
    })

    expect(result.current.status).toBe('saved')
    expect(result.current.statusLabel).toBe('Enregistré')
    expect(result.current.value).toBe('CONTACTED')
    expect(result.current.isSaving).toBe(false)

    // Le badge "Enregistré" s'efface après le délai.
    act(() => {
      vi.advanceTimersByTime(1500)
    })
    expect(result.current.status).toBe('idle')
    expect(result.current.statusLabel).toBe('')
  })

  it('ROLLBACK : restaure l’ancienne valeur et passe en "error" si le commit échoue', async () => {
    const boom = new Error('500')
    const commit = vi.fn(() => Promise.reject(boom))
    const onError = vi.fn()
    const { result } = renderHook(() => useOptimisticSave('NEW', { onError }))

    let outcome
    await act(async () => {
      outcome = await result.current.save('CONTACTED', commit)
    })

    // Rollback complet vers la valeur serveur d'origine.
    expect(result.current.value).toBe('NEW')
    expect(result.current.status).toBe('error')
    expect(result.current.isSaving).toBe(false)
    expect(result.current.error).toBe(boom)
    expect(onError).toHaveBeenCalledWith(boom)
    // save() ne rejette jamais — il renvoie un résultat.
    expect(outcome.ok).toBe(false)
  })

  it('expose une affordance « ligne en cours » (opacité réduite + occupé) seulement pendant le save', async () => {
    let resolveCommit
    const commit = vi.fn(() => new Promise((res) => { resolveCommit = res }))
    const { result } = renderHook(() => useOptimisticSave('NEW'))

    // Au repos : aucune atténuation.
    expect(result.current.rowProps['aria-busy']).toBe(false)
    expect(result.current.rowProps.className).toBe('')

    act(() => {
      result.current.save('CONTACTED', commit)
    })

    // Pendant : aria-busy + classe d'opacité ~50 % + spinner signalé.
    expect(result.current.rowProps['aria-busy']).toBe(true)
    expect(result.current.rowProps.className).toMatch(/opacity-50/)
    expect(result.current.rowProps['data-saving']).toBe(true)

    await act(async () => {
      resolveCommit({})
    })
    expect(result.current.rowProps['aria-busy']).toBe(false)
  })

  it('suit la nouvelle valeur serveur quand elle change hors enregistrement', () => {
    const { result, rerender } = renderHook(
      ({ v }) => useOptimisticSave(v),
      { initialProps: { v: 'NEW' } },
    )
    expect(result.current.value).toBe('NEW')
    rerender({ v: 'SIGNED' })
    expect(result.current.value).toBe('SIGNED')
  })

  it('le commit reçoit la valeur optimiste en argument', async () => {
    const commit = vi.fn(() => Promise.resolve())
    const { result } = renderHook(() => useOptimisticSave('NEW'))
    await act(async () => {
      await result.current.save('FOLLOW_UP', commit)
    })
    expect(commit).toHaveBeenCalledWith('FOLLOW_UP')
  })

  it('un échec puis un nouveau succès repart proprement de "saved"', async () => {
    const fail = vi.fn(() => Promise.reject(new Error('x')))
    const ok = vi.fn(() => Promise.resolve())
    const { result } = renderHook(() => useOptimisticSave('NEW'))

    await act(async () => {
      await result.current.save('CONTACTED', fail)
    })
    expect(result.current.status).toBe('error')
    expect(result.current.value).toBe('NEW')

    await act(async () => {
      await result.current.save('CONTACTED', ok)
    })
    expect(result.current.status).toBe('saved')
    expect(result.current.value).toBe('CONTACTED')
    expect(result.current.error).toBe(null)
  })
})
