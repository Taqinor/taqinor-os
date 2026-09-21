import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/reportingApi', () => ({
  default: {
    search: vi.fn(() => Promise.resolve({
      data: {
        groups: [
          { type: 'devis', label: 'Devis', results: [{ id: 3, label: 'DV-2026-001', sublabel: 'M. Reda' }] },
          { type: 'lead', label: 'Leads', results: [{ id: 8, label: 'Lead Casa' }] },
          // Type NON partageable : doit être filtré.
          { type: 'facture', label: 'Factures', results: [{ id: 1, label: 'FA-1' }] },
        ],
      },
    })),
  },
}))
vi.mock('../../api/messagesApi', () => ({
  default: {
    shareRecord: vi.fn(() => Promise.resolve({ data: { id: 50, shared_label: 'DV-2026-001', shared_url: '/ventes/devis' } })),
  },
}))
vi.mock('../../lib/toast', () => ({ toastError: vi.fn() }))

import reportingApi from '../../api/reportingApi'
import messagesApi from '../../api/messagesApi'
import ShareRecord from './ShareRecord'

beforeEach(() => vi.clearAllMocks())

describe('ShareRecord (S19)', () => {
  it('ouvre le sélecteur et liste seulement les types partageables', async () => {
    render(<ShareRecord conversationId={1} />)
    await userEvent.click(screen.getByLabelText('Partager un enregistrement'))
    await userEvent.type(screen.getByLabelText('Rechercher un enregistrement'), 'reda')
    await waitFor(() => expect(reportingApi.search).toHaveBeenCalledWith('reda'))
    expect(await screen.findByText('DV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('Lead Casa')).toBeInTheDocument()
    // Factures (non partageable) ne doit pas apparaître.
    expect(screen.queryByText('FA-1')).toBeNull()
  })

  it('partage un devis : envoie record_type/record_id et remonte le message', async () => {
    const onShared = vi.fn()
    render(<ShareRecord conversationId={42} onShared={onShared} />)
    await userEvent.click(screen.getByLabelText('Partager un enregistrement'))
    await userEvent.type(screen.getByLabelText('Rechercher un enregistrement'), 'reda')
    const result = await screen.findByText('DV-2026-001')
    await userEvent.click(result)
    await waitFor(() => expect(messagesApi.shareRecord).toHaveBeenCalledWith({
      conversation: 42, record_type: 'devis', record_id: 3,
    }))
    await waitFor(() => expect(onShared).toHaveBeenCalledWith(
      expect.objectContaining({ id: 50, shared_label: 'DV-2026-001' }),
    ))
  })

  it('le bouton est désactivé sans conversation', () => {
    render(<ShareRecord conversationId={null} />)
    expect(screen.getByLabelText('Partager un enregistrement')).toBeDisabled()
  })
})
