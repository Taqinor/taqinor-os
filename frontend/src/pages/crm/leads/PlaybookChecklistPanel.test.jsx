// NTCRM13 — Playbook checklist widget on the lead fiche: a commercial sees
// and checks tasks for the current stage.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../../api/axios'
import PlaybookChecklistPanel from './PlaybookChecklistPanel'

describe('PlaybookChecklistPanel (NTCRM13)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('lists tasks for the lead and lets a commercial check one', async () => {
    api.get.mockResolvedValue({
      data: [
        {
          id: 1, tache: 10, tache_libelle: 'Appeler le client',
          tache_obligatoire: true, fait: false, fait_par_nom: null,
        },
      ],
    })
    api.post.mockResolvedValue({ data: {} })

    render(<PlaybookChecklistPanel leadId={99} />)
    expect(await screen.findByText('Appeler le client')).toBeInTheDocument()
    expect(screen.getByText('obligatoire')).toBeInTheDocument()

    await userEvent.click(screen.getByRole('checkbox'))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/leads/99/playbook/', { tache: 10, fait: true },
    ))
  })

  it('renders nothing when there is no active playbook for this stage', async () => {
    api.get.mockResolvedValue({ data: [] })
    const { container } = render(<PlaybookChecklistPanel leadId={100} />)
    await waitFor(() => expect(api.get).toHaveBeenCalled())
    expect(container.querySelector('[data-testid="playbook-checklist-panel"]')).toBeNull()
  })
})
