import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ZSAV6 — tableau « Action requise » : tickets ouverts groupés par action
   attendue. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: { getSavFileAction: vi.fn(), getTickets: vi.fn() },
}))

import savApi from '../../api/savApi'
import SavActionBoardPage from './SavActionBoardPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SavActionBoardPage', () => {
  it('affiche les buckets avec leurs comptes et les tickets référencés', async () => {
    savApi.getSavFileAction.mockResolvedValue({
      data: {
        buckets: {
          a_repondre: { count: 1, ids: [1] },
          a_planifier: { count: 0, ids: [] },
          a_relancer: { count: 0, ids: [] },
          a_cloturer: { count: 0, ids: [] },
          sans_action: { count: 0, ids: [] },
        },
      },
    })
    savApi.getTickets.mockResolvedValue({
      data: [{ id: 1, reference: 'SAV-001', client_nom: 'ACME' }],
    })
    render(<MemoryRouter><SavActionBoardPage /></MemoryRouter>)
    expect(await screen.findByText('À répondre')).toBeInTheDocument()
    expect(await screen.findByText(/SAV-001/)).toBeInTheDocument()
  })

  it('affiche "Aucun ticket." pour un bucket vide', async () => {
    savApi.getSavFileAction.mockResolvedValue({
      data: {
        buckets: {
          a_repondre: { count: 0, ids: [] },
          a_planifier: { count: 0, ids: [] },
          a_relancer: { count: 0, ids: [] },
          a_cloturer: { count: 0, ids: [] },
          sans_action: { count: 0, ids: [] },
        },
      },
    })
    render(<MemoryRouter><SavActionBoardPage /></MemoryRouter>)
    expect((await screen.findAllByText('Aucun ticket.')).length).toBe(5)
  })
})
