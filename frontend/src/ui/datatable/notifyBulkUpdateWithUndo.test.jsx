// NTUX6 — notifyBulkUpdateWithUndo : toast succès + action « Annuler » (10s),
// conflit optimistic-lock affiche une erreur claire au lieu d'annuler en silence.
import { describe, it, expect, vi, beforeEach } from 'vitest'

const toastSuccessMock = vi.fn()
const toastErrorMock = vi.fn()
vi.mock('../confirm', () => ({ toast: { success: (...a) => toastSuccessMock(...a), error: (...a) => toastErrorMock(...a) } }))

import { notifyBulkUpdateWithUndo } from './notifyBulkUpdateWithUndo.js'
import { UNDO_WINDOW_MS } from './bulkEditUndo.js'

beforeEach(() => { toastSuccessMock.mockReset(); toastErrorMock.mockReset() })

describe('notifyBulkUpdateWithUndo (NTUX6)', () => {
  it('ne fait rien si aucune ligne mise à jour', () => {
    notifyBulkUpdateWithUndo({ updated: [], failed: [] }, {})
    expect(toastSuccessMock).not.toHaveBeenCalled()
  })

  it('toast de succès avec fenêtre d\'annulation de 10s et action « Annuler »', () => {
    const result = { updated: [{ id: 1, before: 'a', after: 'b', updated_at: 't1' }], failed: [] }
    notifyBulkUpdateWithUndo(result, { fieldLabel: 'statut', onUndo: vi.fn() })
    expect(toastSuccessMock).toHaveBeenCalledTimes(1)
    const [message, opts] = toastSuccessMock.mock.calls[0]
    expect(message).toMatch(/1 ligne/)
    expect(opts.duration).toBe(UNDO_WINDOW_MS)
    expect(opts.action.label).toBe('Annuler')
  })

  it('cliquer « Annuler » restaure exactement l\'état AVANT capturé (pas de nouvelle lecture serveur)', () => {
    const result = {
      updated: [
        { id: 1, before: 'brouillon', after: 'accepte', updated_at: 't1' },
        { id: 2, before: 'envoye', after: 'accepte', updated_at: 't2' },
      ],
      failed: [],
    }
    const onUndo = vi.fn()
    notifyBulkUpdateWithUndo(result, {
      onUndo, getCurrentUpdatedAt: (id) => (id === 1 ? 't1' : 't2'),
    })
    const [, opts] = toastSuccessMock.mock.calls[0]
    opts.action.onClick()
    expect(onUndo).toHaveBeenCalledWith(result.updated)
  })

  it('un enregistrement modifié entretemps refuse l\'annulation pour CETTE ligne avec un message clair', () => {
    const result = {
      updated: [{ id: 1, before: 'brouillon', after: 'accepte', updated_at: 't1' }],
      failed: [],
    }
    const onUndo = vi.fn()
    notifyBulkUpdateWithUndo(result, { onUndo, getCurrentUpdatedAt: () => 't1-changed' })
    const [, opts] = toastSuccessMock.mock.calls[0]
    opts.action.onClick()
    expect(onUndo).not.toHaveBeenCalled()
    expect(toastErrorMock).toHaveBeenCalledTimes(1)
    expect(toastErrorMock.mock.calls[0][0]).toMatch(/modifiée entretemps/)
  })
})
