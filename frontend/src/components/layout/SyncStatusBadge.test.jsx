import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* NTMOB3 — le badge de synchro global : masqué quand tout est synchronisé et
   le réseau présent, visible avec le compteur d'opérations en attente dès
   qu'on passe hors ligne, et en état « Erreur de synchro » quand une op a été
   refusée par le serveur. Il LIT l'outbox partagé (aucun 2ᵉ compteur). */

const { useFieldOutbox } = vi.hoisted(() => ({ useFieldOutbox: vi.fn() }))
vi.mock('../../features/installations/offline/useFieldOutbox', () => ({
  useFieldOutbox,
}))

import SyncStatusBadge from './SyncStatusBadge'
import { syncState } from './syncState'

function etatOutbox(over = {}) {
  return {
    online: true,
    pending: 0,
    pendingPhotos: 0,
    failed: [],
    flushing: false,
    flush: vi.fn(),
    ...over,
  }
}

beforeEach(() => { useFieldOutbox.mockReset() })
afterEach(() => cleanup())

describe('NTMOB3 syncState', () => {
  it('agrège les photos dans le même compteur', () => {
    const s = syncState({
      online: true, pending: 2, pendingPhotos: 1, failedCount: 0,
    })
    expect(s.key).toBe('attente')
    expect(s.count).toBe(3)
    expect(s.label).toBe('3 opérations en attente')
  })

  it('accorde le singulier', () => {
    expect(syncState({
      online: false, pending: 1, pendingPhotos: 0, failedCount: 0,
    }).label).toBe('1 opération en attente')
  })

  it('une erreur serveur prime sur le compteur d’attente', () => {
    const s = syncState({
      online: true, pending: 4, pendingPhotos: 0, failedCount: 1,
    })
    expect(s.key).toBe('erreur')
    expect(s.label).toBe('Erreur de synchro')
  })

  it('rien en file = synchronisé', () => {
    expect(syncState({
      online: true, pending: 0, pendingPhotos: 0, failedCount: 0,
    }).key).toBe('ok')
  })
})

describe('NTMOB3 SyncStatusBadge', () => {
  it('reste masqué quand tout est synchronisé et le réseau présent', () => {
    useFieldOutbox.mockReturnValue(etatOutbox())
    render(<SyncStatusBadge />)
    expect(screen.queryByTestId('sync-status-badge')).not.toBeInTheDocument()
  })

  it('apparaît hors ligne avec le compteur d’opérations en attente', () => {
    useFieldOutbox.mockReturnValue(etatOutbox({ online: false, pending: 2 }))
    render(<SyncStatusBadge />)
    const badge = screen.getByTestId('sync-status-badge')
    expect(badge).toHaveAttribute('data-sync-state', 'attente')
    expect(badge).toHaveAttribute('aria-label', '2 opérations en attente')
    expect(screen.getByText('2')).toBeInTheDocument()
  })

  it('reste visible hors ligne même sans opération en file', () => {
    useFieldOutbox.mockReturnValue(etatOutbox({ online: false }))
    render(<SyncStatusBadge />)
    expect(screen.getByTestId('sync-status-badge'))
      .toHaveAttribute('data-sync-state', 'ok')
  })

  it('signale une erreur de synchro quand une op est refusée', () => {
    useFieldOutbox.mockReturnValue(etatOutbox({
      failed: [{
        client_op_id: 'op-1',
        op_type: 'intervention.checkin',
        serverError: 'Chantier introuvable',
      }],
    }))
    render(<SyncStatusBadge />)
    expect(screen.getByTestId('sync-status-badge'))
      .toHaveAttribute('data-sync-state', 'erreur')
  })
})
