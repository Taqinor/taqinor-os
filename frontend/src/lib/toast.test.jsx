import { describe, it, expect, vi } from 'vitest'

vi.mock('../ui/Toaster', () => ({
  toast: {
    success: vi.fn(() => 'toast-id'),
    error: vi.fn(() => 'toast-id'),
    info: vi.fn(() => 'toast-id'),
    warning: vi.fn(() => 'toast-id'),
    promise: vi.fn(),
  },
}))

import {
  toastError, toastSuccess, toastInfo, toastWarning, toastDestructive,
  DESTRUCTIVE_UNDO_MIN_MS, subscribeAssertiveAnnouncer,
} from './toast'
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

// VX130 — toastInfo/toastWarning appellent désormais `toast.info`/`toast.warning`
// (typés, stylés) plutôt que le `toast()` générique / `toast.error` détourné.
describe('VX130 — toastInfo / toastWarning : registres dédiés (pas un vocabulaire binaire)', () => {
  it('toastInfo appelle toast.info', () => {
    toastInfo('Nouvelle version disponible.')
    expect(toast.info).toHaveBeenCalledWith('Nouvelle version disponible.', {})
  })

  it('toastWarning appelle toast.warning', () => {
    toastWarning('Stock bas — 2 unités restantes.')
    expect(toast.warning).toHaveBeenCalledWith('Stock bas — 2 unités restantes.', {})
  })
})

// VX130 — le registre destructif que toastWithUndo n'offrait pas : délai
// d'annulation TOUJOURS ≥ 6 s, rendu visuel danger (toast.error).
describe('VX130 — toastDestructive : registre destructif à délai prolongé', () => {
  it('utilise toast.error (rendu danger) avec une action Annuler', () => {
    toastDestructive({ message: '1 lead supprimé définitivement.' })
    expect(toast.error).toHaveBeenCalledWith(
      '1 lead supprimé définitivement.',
      expect.objectContaining({ duration: DESTRUCTIVE_UNDO_MIN_MS, action: expect.any(Object) }),
    )
  })

  it('impose un délai ≥ 6 s même si un duration plus court est demandé', () => {
    toastDestructive({ message: 'Suppression.', duration: 2000 })
    const lastCall = toast.error.mock.calls.at(-1)
    expect(lastCall[1].duration).toBeGreaterThanOrEqual(DESTRUCTIVE_UNDO_MIN_MS)
  })

  it('un duration plus long que le minimum est respecté', () => {
    toastDestructive({ message: 'Suppression.', duration: 9000 })
    const lastCall = toast.error.mock.calls.at(-1)
    expect(lastCall[1].duration).toBe(9000)
  })
})
