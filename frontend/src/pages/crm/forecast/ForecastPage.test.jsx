// NTCRM7 — Forecast screen: recategorize inline, row total recomputes without reload.
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
import ForecastPage from './ForecastPage'

const rollupFixture = (commitTotal) => ({
  equipes: [{
    equipe_id: 1,
    nom: 'Équipe test',
    ecart_vs_objectif: null,
    total: commitTotal,
    totals: { commit: commitTotal },
    commerciaux: [{
      owner_id: 5, nom: 'com_a', totals: { commit: commitTotal },
    }],
  }],
  total_societe: { commit: commitTotal },
})

describe('ForecastPage (NTCRM7)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
  })

  it('renders the team rollup with a per-commercial row and team subtotal', async () => {
    api.get.mockResolvedValue({ data: rollupFixture(10000) })
    render(<ForecastPage />)
    expect(await screen.findByText('Équipe test')).toBeInTheDocument()
    expect(screen.getByTestId('ligne-5')).toHaveTextContent('com_a')
    expect(screen.getByTestId('ligne-5')).toHaveTextContent('10000')
  })

  it('recategorizing a lead updates the row total without a page reload', async () => {
    api.get
      .mockResolvedValueOnce({ data: rollupFixture(10000) })
      .mockResolvedValueOnce({ data: rollupFixture(25000) })
    api.post.mockResolvedValue({ data: { id: 99 } })

    render(<ForecastPage />)
    await screen.findByText('Équipe test')

    await userEvent.type(screen.getByPlaceholderText('ID lead'), '42')
    await userEvent.click(screen.getByRole('button', { name: /Recatégoriser/i }))

    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/crm/forecast-entries/', expect.objectContaining({ lead: '42' }),
    ))
    // Second GET (reload) reflects the updated total — no window.location change.
    await waitFor(() => expect(api.get).toHaveBeenCalledTimes(2))
    expect(await screen.findByText('25000')).toBeInTheDocument()
  })
})
