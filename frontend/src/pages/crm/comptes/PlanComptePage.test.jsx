// NTCRM11 — Plan de compte screen: fill and save a complete plan in one session.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

vi.mock('../../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn(), patch: vi.fn() },
}))
vi.mock('../../../ui/confirm', () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}))

import api from '../../../api/axios'
import PlanComptePage from './PlanComptePage'

describe('PlanComptePage (NTCRM11)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    api.get.mockResolvedValue({ data: { results: [] } })
  })

  it('creates a new plan de compte with objectives and SWOT in one session', async () => {
    api.post.mockResolvedValueOnce({ data: { id: 3 } })
    api.get
      .mockResolvedValueOnce({ data: { results: [] } })
      .mockResolvedValueOnce({
        data: {
          id: 3, objectifs_strategiques: 'Grandir', revues: [],
          swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
        },
      })

    render(<PlanComptePage clientId={11} />)
    await screen.findByTestId('plan-compte-screen')

    await userEvent.type(
      screen.getByPlaceholderText('Objectifs stratégiques'), 'Grandir')
    await userEvent.click(
      screen.getByRole('button', { name: /Enregistrer le plan de compte/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/plans-compte/',
      expect.objectContaining({ client: 11, objectifs_strategiques: 'Grandir' }),
    ))
  })

  it('shows the reviews timeline when the plan already has revues', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        id: 5, objectifs_strategiques: '', revues: [
          { id: 1, date_revue: '2026-07-01', decisions: 'Relancer' },
        ],
        swot_forces: [], swot_faiblesses: [], swot_opportunites: [], swot_menaces: [],
      },
    })
    render(<PlanComptePage clientId={11} planId={5} />)
    expect(await screen.findByText('Relancer')).toBeInTheDocument()
  })
})
