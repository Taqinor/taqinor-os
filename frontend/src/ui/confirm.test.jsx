import { describe, it, expect, vi, beforeEach } from 'vitest'
import { renderHook, act } from '@testing-library/react'

// On isole le helper de ses dépendances réelles : le contexte de confirmation
// (provider Radix monté à la racine) et sonner (toasts). Les mocks reproduisent
// le contrat public de chacun pour vérifier que `confirm.jsx` se contente de les
// envelopper sans réimplémenter la primitive. `vi.hoisted` rend les espions
// disponibles aux usines `vi.mock` (hissées en tête de fichier).
const { confirmSpy, toastMock } = vi.hoisted(() => ({
  confirmSpy: vi.fn(() => Promise.resolve(true)),
  toastMock: {
    success: vi.fn(),
    error: vi.fn(),
    message: vi.fn(),
    promise: vi.fn(),
  },
}))
vi.mock('../providers/confirm-context', () => ({
  useConfirm: () => confirmSpy,
}))
vi.mock('./Toaster', () => ({ toast: toastMock }))

import { useConfirmDialog, toast, toastPromise } from './confirm'

beforeEach(() => {
  confirmSpy.mockClear()
  confirmSpy.mockResolvedValue(true)
  toastMock.success.mockClear()
  toastMock.error.mockClear()
  toastMock.message.mockClear()
  toastMock.promise.mockClear()
})

describe('useConfirmDialog (helper L152)', () => {
  it('expose confirm + confirmDelete et délègue au contexte useConfirm', async () => {
    const { result } = renderHook(() => useConfirmDialog())
    expect(typeof result.current.confirm).toBe('function')
    expect(typeof result.current.confirmDelete).toBe('function')

    let ok
    await act(async () => {
      ok = await result.current.confirm({ title: 'Continuer ?' })
    })
    expect(ok).toBe(true)
    expect(confirmSpy).toHaveBeenCalledWith(
      expect.objectContaining({ title: 'Continuer ?' }),
    )
  })

  it('confirmDelete préremplit les libellés destructifs FR', async () => {
    const { result } = renderHook(() => useConfirmDialog())
    await act(async () => {
      await result.current.confirmDelete({ description: 'Devis 42' })
    })
    const opts = confirmSpy.mock.calls[0][0]
    expect(opts.destructive).toBe(true)
    expect(opts.confirmLabel).toBe('Supprimer')
    expect(opts.description).toBe('Devis 42')
    // Un appelant peut passer juste une chaîne de titre.
    confirmSpy.mockClear()
    await act(async () => {
      await result.current.confirmDelete('Cet élément ?')
    })
    expect(confirmSpy.mock.calls[0][0].title).toBe('Cet élément ?')
  })

  it('propage un refus (Promise<false>) sans planter', async () => {
    confirmSpy.mockResolvedValueOnce(false)
    const { result } = renderHook(() => useConfirmDialog())
    let ok
    await act(async () => {
      ok = await result.current.confirm('Vraiment ?')
    })
    expect(ok).toBe(false)
  })
})

describe('toast (réexport) + toastPromise (helper L152)', () => {
  it('réexporte toast.success / toast.error depuis Toaster', () => {
    expect(toast.success).toBe(toastMock.success)
    expect(toast.error).toBe(toastMock.error)
  })

  it('toastPromise relaie la promesse et des messages FR par défaut', async () => {
    const p = Promise.resolve({ id: 1 })
    toastPromise(p)
    expect(toastMock.promise).toHaveBeenCalledTimes(1)
    const [passedPromise, messages] = toastMock.promise.mock.calls[0]
    expect(passedPromise).toBe(p)
    expect(messages.loading).toBe('Enregistrement…')
    expect(typeof messages.success).toBe('string')
    expect(typeof messages.error).toBe('string')
  })

  it('toastPromise accepte des messages personnalisés', () => {
    const p = Promise.resolve()
    toastPromise(p, { loading: 'Envoi…', success: 'Envoyé', error: 'Échec' })
    const [, messages] = toastMock.promise.mock.calls[0]
    expect(messages.loading).toBe('Envoi…')
    expect(messages.success).toBe('Envoyé')
    expect(messages.error).toBe('Échec')
  })

  it('toastPromise renvoie la promesse pour permettre le chaînage/await', async () => {
    const p = Promise.resolve('done')
    const returned = toastPromise(p)
    await expect(returned).resolves.toBe('done')
  })
})
