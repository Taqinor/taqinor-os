import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR157 — Onglet « Rétention (Discuter) » : politique de rétention par type
   de conversation (DM/canal) + historique des purges (RetentionSweepRun). */

vi.mock('../../api/messagesApi', () => ({
  default: {
    retention: {
      list: vi.fn(),
      create: vi.fn(),
      update: vi.fn(),
      historique: vi.fn(),
    },
  },
}))

import messagesApi from '../../api/messagesApi'
import ChatRetentionSection from './ChatRetentionSection'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('ChatRetentionSection (WIR157)', () => {
  it('affiche les politiques existantes et l’historique des purges', async () => {
    messagesApi.retention.list.mockResolvedValue({
      data: [{ id: 5, conversation_kind: 'dm', retention_months: 12 }],
    })
    messagesApi.retention.historique.mockResolvedValue({
      data: [{ id: 1, ran_at: '2026-06-21T02:45:00Z', messages_purged: 3 }],
    })
    render(<ChatRetentionSection />)

    expect(await screen.findByLabelText('Messages directs (DM)')).toHaveValue(12)
    expect(screen.getByLabelText('Canaux')).toHaveValue(null)
    expect(await screen.findByText(/3 messages purgés/)).toBeInTheDocument()
  })

  it('pose une nouvelle politique de rétention (create, aucune ligne existante)', async () => {
    messagesApi.retention.list.mockResolvedValue({ data: [] })
    messagesApi.retention.historique.mockResolvedValue({ data: [] })
    messagesApi.retention.create.mockResolvedValue({
      data: { id: 9, conversation_kind: 'channel', retention_months: 24 },
    })
    render(<ChatRetentionSection />)

    const input = await screen.findByLabelText('Canaux')
    await userEvent.type(input, '24')
    const saveButtons = await screen.findAllByRole('button', { name: 'Enregistrer' })
    await userEvent.click(saveButtons[1])
    await waitFor(() => expect(messagesApi.retention.create).toHaveBeenCalledWith(
      { conversation_kind: 'channel', retention_months: 24 }))
  })

  it('met à jour une politique existante (update, pas create)', async () => {
    messagesApi.retention.list.mockResolvedValue({
      data: [{ id: 5, conversation_kind: 'dm', retention_months: 12 }],
    })
    messagesApi.retention.historique.mockResolvedValue({ data: [] })
    messagesApi.retention.update.mockResolvedValue({
      data: { id: 5, conversation_kind: 'dm', retention_months: 6 },
    })
    render(<ChatRetentionSection />)

    const input = await screen.findByLabelText('Messages directs (DM)')
    await userEvent.clear(input)
    await userEvent.type(input, '6')
    const saveButtons = screen.getAllByRole('button', { name: 'Enregistrer' })
    await userEvent.click(saveButtons[0])
    await waitFor(() => expect(messagesApi.retention.update).toHaveBeenCalledWith(
      5, { retention_months: 6 }))
    expect(messagesApi.retention.create).not.toHaveBeenCalled()
  })

  it('affiche un état vide quand l’historique est vide', async () => {
    messagesApi.retention.list.mockResolvedValue({ data: [] })
    messagesApi.retention.historique.mockResolvedValue({ data: [] })
    render(<ChatRetentionSection />)
    expect(await screen.findByText(/Aucune exécution enregistrée/)).toBeInTheDocument()
  })
})
