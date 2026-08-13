// NTMOB3 — le badge global de synchro : silencieux en ligne/file vide, visible
// avec le COMPTEUR dès qu'une action est posée hors-ligne, distinct quand une
// op a été refusée par le serveur, et journal cliquable des ops en attente.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent, within } from '@testing-library/react'

// L'outbox terrain réelle (IndexedDB/localStorage + axios) est remplacée par
// une file en mémoire pilotable : `useFieldOutbox` importe CE module, donc le
// hook et le composant lisent la même fausse file — aucun double état.
const { file, filePhotos } = vi.hoisted(() => ({
  file: { ops: [] },
  filePhotos: { ops: [] },
}))
vi.mock('../installations/offline/fieldOutbox', () => ({
  fieldOutbox: {
    pending: async () => [...file.ops],
    flush: async () => ({ flushed: 0, failed: 0, remaining: file.ops.length }),
    discard: async (id) => { file.ops = file.ops.filter((o) => o.client_op_id !== id) },
  },
  binaryOutbox: {
    pending: async () => [...filePhotos.ops],
    flush: async () => ({ flushed: 0, failed: 0, remaining: filePhotos.ops.length }),
    discard: async () => {},
    persistent: true,
  },
}))

import SyncStatusBadge from './SyncStatusBadge'

function setOnline(valeur) {
  Object.defineProperty(window.navigator, 'onLine', {
    configurable: true, value: valeur,
  })
}

beforeEach(() => {
  file.ops = []
  filePhotos.ops = []
  setOnline(true)
})
afterEach(() => cleanup())

describe('NTMOB3 — SyncStatusBadge', () => {
  it('ne rend rien en ligne avec une file vide (zéro bruit dans l’en-tête)', async () => {
    render(<SyncStatusBadge />)
    await waitFor(() => expect(screen.queryByTestId('sync-status-badge')).toBeNull())
  })

  it('affiche le compteur des actions posées hors-ligne', async () => {
    setOnline(false)
    file.ops = [
      { client_op_id: 'a', op_type: 'intervention.checkin' },
      { client_op_id: 'b', op_type: 'chantier.cocher_checklist' },
    ]
    filePhotos.ops = [
      { client_op_id: 'c', op_type: 'intervention.photo', queuedAt: '2026-08-13T09:30:00Z' },
    ]
    render(<SyncStatusBadge />)
    const badge = await screen.findByTestId('sync-status-badge')
    // 2 ops JSON + 1 photo = 3, une seule file, un seul badge (EZ8).
    expect(badge).toHaveTextContent('3')
    expect(badge).toHaveAttribute(
      'aria-label', expect.stringContaining('3 opérations en attente'))
  })

  it('signale « Erreur de synchro » quand le serveur a refusé une op', async () => {
    file.ops = [{
      client_op_id: 'a',
      op_type: 'intervention.signer_client',
      serverError: 'Chantier déjà clôturé.',
      attempts: 2,
    }]
    render(<SyncStatusBadge />)
    const badge = await screen.findByTestId('sync-status-badge')
    expect(badge).toHaveAttribute(
      'aria-label', expect.stringContaining('Erreur de synchro'))
  })

  it('ouvre le journal des opérations en attente au clic', async () => {
    setOnline(false)
    file.ops = [{ client_op_id: 'a', op_type: 'intervention.checkin' }]
    render(<SyncStatusBadge />)
    fireEvent.click(await screen.findByTestId('sync-status-badge'))
    const journal = await screen.findByTestId('sync-status-libelle')
    expect(journal).toHaveTextContent('Hors ligne')
    expect(await screen.findByText('intervention.checkin')).toBeInTheDocument()
  })

  it('permet d’abandonner explicitement une op refusée', async () => {
    file.ops = [{
      client_op_id: 'a', op_type: 'intervention.reserve', serverError: 'Refusée.',
    }]
    render(<SyncStatusBadge />)
    fireEvent.click(await screen.findByTestId('sync-status-badge'))
    const ligne = (await screen.findByText('intervention.reserve')).closest('li')
    fireEvent.click(within(ligne).getByRole('button', { name: 'Abandonner' }))
    await waitFor(() => expect(file.ops).toHaveLength(0))
  })
})
