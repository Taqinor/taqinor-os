import { describe, it, expect, vi } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useStaleGuard } from './useStaleGuard'

/* VX243(c) — garde d'édition périmée (stale-write).
   Règle : au submit, un GET léger relit `updated_at` ; s'il a changé depuis
   l'ouverture (édition concurrente), `checkBeforeSave()` renvoie false et
   expose `staleInfo` (bannière AVANT le PATCH). « Enregistrer quand même »
   arme un forçage à usage unique qui laisse le submit suivant passer. */
describe('useStaleGuard (VX243c)', () => {
  it('laisse passer quand rien n\'a changé (même updated_at)', async () => {
    const fetchLatest = vi.fn().mockResolvedValue({ updated_at: 'T0' })
    const { result } = renderHook(() =>
      useStaleGuard({ openedAt: 'T0', fetchLatest }))
    let ok
    await act(async () => { ok = await result.current.checkBeforeSave() })
    expect(ok).toBe(true)
    expect(result.current.staleInfo).toBeNull()
  })

  it('bloque et expose staleInfo quand updated_at a changé (2 onglets)', async () => {
    const fetchLatest = vi.fn().mockResolvedValue({
      updated_at: 'T1', updated_by_nom: 'Sami',
    })
    const { result } = renderHook(() =>
      useStaleGuard({ openedAt: 'T0', fetchLatest }))
    let ok
    await act(async () => { ok = await result.current.checkBeforeSave() })
    expect(ok).toBe(false)
    expect(result.current.staleInfo).toEqual({ by: 'Sami', at: 'T1' })
  })

  it('« Enregistrer quand même » (force) laisse passer le submit suivant', async () => {
    const fetchLatest = vi.fn().mockResolvedValue({ updated_at: 'T1' })
    const { result } = renderHook(() =>
      useStaleGuard({ openedAt: 'T0', fetchLatest }))
    await act(async () => { await result.current.checkBeforeSave() })
    expect(result.current.staleInfo).not.toBeNull()
    act(() => { result.current.force() })
    expect(result.current.staleInfo).toBeNull()
    let ok
    await act(async () => { ok = await result.current.checkBeforeSave() })
    expect(ok).toBe(true) // le forçage à usage unique a couvert CE submit
  })

  it('ne fait AUCUNE requête à la création (openedAt absent)', async () => {
    const fetchLatest = vi.fn()
    const { result } = renderHook(() =>
      useStaleGuard({ openedAt: undefined, fetchLatest }))
    let ok
    await act(async () => { ok = await result.current.checkBeforeSave() })
    expect(ok).toBe(true)
    expect(fetchLatest).not.toHaveBeenCalled()
  })

  it('une vérification en échec ne bloque jamais un enregistrement légitime', async () => {
    const fetchLatest = vi.fn().mockRejectedValue(new Error('réseau'))
    const { result } = renderHook(() =>
      useStaleGuard({ openedAt: 'T0', fetchLatest }))
    let ok
    await act(async () => { ok = await result.current.checkBeforeSave() })
    expect(ok).toBe(true)
  })
})
