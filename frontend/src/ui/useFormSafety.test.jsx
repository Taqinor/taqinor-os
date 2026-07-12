import { describe, it, expect, vi, afterEach } from 'vitest'
import { renderHook } from '@testing-library/react'
import { useFormSafety } from './useFormSafety'

/* VX170 — useFormSafety : la primitive commune qui compose diff générique +
   useDirtyGuard + confirmLeaveIfDirty (+ garde route-level optionnelle). Testé
   hors routeur (comme tout le reste du repo, cf. useNavigationGuard.js) — le
   repli no-op de `useBlocker` s'applique, `dirty`/`guardedClose` restent
   corrects indépendamment de la présence d'un routeur data. */

afterEach(() => {
  vi.restoreAllMocks()
})

describe('useFormSafety — diff générique + fermeture gardée', () => {
  it('dirty=false quand `current` égale `initial`', () => {
    const initial = { nom: 'Ali', email: '' }
    const { result } = renderHook(() => useFormSafety(initial, { ...initial }, vi.fn()))
    expect(result.current.dirty).toBe(false)
  })

  it('dirty=true dès qu’un champ diverge de `initial`', () => {
    const initial = { nom: 'Ali', email: '' }
    const { result } = renderHook(() => useFormSafety(initial, { nom: 'Ali', email: 'a@b.ma' }, vi.fn()))
    expect(result.current.dirty).toBe(true)
  })

  it('guardedClose ferme SANS confirmation quand non modifié', () => {
    const onClose = vi.fn()
    const confirmSpy = vi.spyOn(window, 'confirm')
    const initial = { nom: 'Ali' }
    const { result } = renderHook(() => useFormSafety(initial, { ...initial }, onClose))

    result.current.guardedClose()

    expect(confirmSpy).not.toHaveBeenCalled()
    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('guardedClose demande confirmation quand modifié — refus = onClose jamais appelé', () => {
    const onClose = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(false)
    const initial = { nom: 'Ali' }
    const { result } = renderHook(() => useFormSafety(initial, { nom: 'Autre' }, onClose))

    result.current.guardedClose()

    expect(window.confirm).toHaveBeenCalledTimes(1)
    expect(onClose).not.toHaveBeenCalled()
  })

  it('guardedClose demande confirmation quand modifié — accord = onClose appelé', () => {
    const onClose = vi.fn()
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    const initial = { nom: 'Ali' }
    const { result } = renderHook(() => useFormSafety(initial, { nom: 'Autre' }, onClose))

    result.current.guardedClose()

    expect(onClose).toHaveBeenCalledTimes(1)
  })

  it('snapshot renvoie l’état courant tel quel', () => {
    const current = { nom: 'Ali' }
    const { result } = renderHook(() => useFormSafety({ nom: '' }, current, vi.fn()))
    expect(result.current.snapshot).toBe(current)
  })
})
