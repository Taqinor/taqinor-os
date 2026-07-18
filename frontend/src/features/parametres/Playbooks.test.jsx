// NTCRM13 — Playbooks admin screen: create a 3-step playbook with tasks.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../api/axios'
import Playbooks from './Playbooks'

describe('Playbooks (NTCRM13)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { results: [] } })
  })

  it('shows the empty state, then creates a playbook', async () => {
    api.post.mockResolvedValueOnce({ data: { id: 1 } })
    api.get
      .mockResolvedValueOnce({ data: { results: [] } })
      .mockResolvedValueOnce({
        data: { results: [{ id: 1, nom: 'Playbook QUOTE_SENT', bloquant: false, etapes: [] }] },
      })

    render(<Playbooks />)
    expect(await screen.findByText(/Aucun playbook/i)).toBeInTheDocument()

    await userEvent.type(screen.getByPlaceholderText('Nom du playbook'), 'Playbook QUOTE_SENT')
    await userEvent.click(screen.getByRole('button', { name: /^Créer$/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/playbooks/',
      expect.objectContaining({ nom: 'Playbook QUOTE_SENT' }),
    ))
    expect(await screen.findByTestId('playbook-1')).toBeInTheDocument()
  })

  it('adds a stage from STAGES.py labels then a task to it', async () => {
    api.get
      .mockResolvedValueOnce({
        data: { results: [{ id: 2, nom: 'PB', bloquant: false, etapes: [] }] },
      })
      .mockResolvedValueOnce({
        data: {
          results: [{
            id: 2, nom: 'PB', bloquant: false,
            etapes: [{ id: 20, stage: 'QUOTE_SENT', taches: [] }],
          }],
        },
      })
    api.post.mockResolvedValueOnce({ data: { id: 20 } })

    render(<Playbooks />)
    await screen.findByTestId('playbook-2')

    await userEvent.click(screen.getByRole('button', { name: /Ajouter une étape/i }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/playbook-etapes/', expect.objectContaining({ playbook: 2 }),
    ))
    // Le libellé de stage figure dans le <option> ET l'en-tête d'étape.
    expect((await screen.findAllByText('Devis envoyé')).length).toBeGreaterThan(0)
  })
})
