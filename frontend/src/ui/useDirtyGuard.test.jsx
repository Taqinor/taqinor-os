import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'
import { useDirtyGuard, confirmLeaveIfDirty, isAnyFormDirty } from './useDirtyGuard'

/* VX170 — repli WebKit `pagehide`/`visibilitychange`→`hidden` : on ne peut pas
   bloquer un `pagehide` (aucune confirmation synchrone n'y survit), donc la
   bonne UX WebKit est de SAUVER un brouillon défensif via `lib/safeStorage`,
   jamais de bloquer. Rétrocompatibilité : les 7+ adoptants qui appellent
   `useDirtyGuard(dirty)` / `useDirtyGuard(dirty, message)` sans 3ᵉ argument ne
   branchent RIEN de nouveau (aucun listener pagehide posé). */

vi.mock('../lib/safeStorage', () => ({ safeSet: vi.fn() }))
import { safeSet } from '../lib/safeStorage'

afterEach(() => {
  vi.clearAllMocks()
})

describe('useDirtyGuard — rétrocompatibilité (sans persist)', () => {
  it('ne pose aucun listener pagehide sans le 3ᵉ argument `persist`', () => {
    renderHook(() => useDirtyGuard(true))
    window.dispatchEvent(new Event('pagehide'))
    expect(safeSet).not.toHaveBeenCalled()
  })
})

describe('useDirtyGuard — persistance défensive WebKit (VX170)', () => {
  it('pagehide + dirty=true -> persiste le dernier snapshot via safeStorage', () => {
    let current = { titre: 'brouillon v1' }
    renderHook(() => useDirtyGuard(true, undefined, {
      key: 'test-key',
      getData: () => current,
    }))

    // Le dernier état est lu AU MOMENT de l'événement (pas à l'abonnement).
    current = { titre: 'brouillon v2' }
    act(() => { window.dispatchEvent(new Event('pagehide')) })

    expect(safeSet).toHaveBeenCalledTimes(1)
    const [key, payload] = safeSet.mock.calls[0]
    expect(key).toBe('test-key')
    expect(payload.data).toEqual({ titre: 'brouillon v2' })
    expect(typeof payload.savedAt).toBe('string')
  })

  it('visibilitychange -> hidden + dirty=true -> persiste aussi', () => {
    renderHook(() => useDirtyGuard(true, undefined, {
      key: 'test-key-2',
      getData: () => ({ champ: 'x' }),
    }))

    Object.defineProperty(document, 'visibilityState', { value: 'hidden', configurable: true })
    act(() => { document.dispatchEvent(new Event('visibilitychange')) })

    expect(safeSet).toHaveBeenCalledWith('test-key-2', expect.objectContaining({ data: { champ: 'x' } }))
  })

  it('non-dirty -> aucun listener posé, aucune persistance sur pagehide', () => {
    renderHook(() => useDirtyGuard(false, undefined, {
      key: 'test-key-3',
      getData: () => ({ champ: 'x' }),
    }))
    window.dispatchEvent(new Event('pagehide'))
    expect(safeSet).not.toHaveBeenCalled()
  })
})

describe('confirmLeaveIfDirty / isAnyFormDirty — inchangés (non-régression)', () => {
  it('confirmLeaveIfDirty renvoie true sans confirmation quand non modifié', () => {
    expect(confirmLeaveIfDirty(false)).toBe(true)
  })

  it('isAnyFormDirty reflète le registre partagé (VX62)', () => {
    expect(isAnyFormDirty()).toBe(false)
    const { unmount } = renderHook(() => useDirtyGuard(true))
    expect(isAnyFormDirty()).toBe(true)
    unmount()
    expect(isAnyFormDirty()).toBe(false)
  })
})
