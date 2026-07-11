import { describe, it, expect, vi } from 'vitest'

vi.mock('../ui/Toaster', () => ({
  toast: {
    success: vi.fn(() => 'toast-id'),
    error: vi.fn(() => 'toast-id'),
    promise: vi.fn(),
  },
}))

import { toastError, toastSuccess, subscribeAssertiveAnnouncer } from './toast'
import { toast } from '../ui/Toaster'

describe('toastError (VX196 — assertive announcer)', () => {
  it('publie le message vers les abonnés assertifs ET appelle toast.error', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeAssertiveAnnouncer(listener)
    toastError('Échec du changement d’étape')
    expect(listener).toHaveBeenCalledWith('Échec du changement d’étape')
    expect(toast.error).toHaveBeenCalledWith('Échec du changement d’étape', {})
    unsubscribe()
  })

  it('ne notifie plus après désabonnement', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeAssertiveAnnouncer(listener)
    unsubscribe()
    toastError('Autre erreur')
    expect(listener).not.toHaveBeenCalled()
  })
})

describe('toastSuccess (reste polite — ne publie rien en assertive)', () => {
  it('n’émet aucune annonce assertive', () => {
    const listener = vi.fn()
    const unsubscribe = subscribeAssertiveAnnouncer(listener)
    toastSuccess('Enregistré.')
    expect(listener).not.toHaveBeenCalled()
    expect(toast.success).toHaveBeenCalledWith('Enregistré.', {})
    unsubscribe()
  })
})
