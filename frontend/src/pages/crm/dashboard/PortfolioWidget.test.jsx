import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* NTCRM29 — widget dashboard commercial « portefeuille de comptes ».
   crmApi mocké. */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getMonPortefeuille: vi.fn(() => Promise.resolve({
      data: {
        count: 2,
        results: [
          { client_id: 1, nom: 'Compte froid', score: 10, label: 'Froid', plan_compte_id: 5 },
          { client_id: 2, nom: 'Compte tiède', score: 50, label: 'Tiède', plan_compte_id: null },
        ],
      },
    })),
  },
}))

import crmApi from '../../../api/crmApi'
import PortfolioWidget from './PortfolioWidget'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function mount() {
  return render(
    <MemoryRouter>
      <PortfolioWidget />
    </MemoryRouter>,
  )
}

describe('PortfolioWidget (NTCRM29)', () => {
  it('liste les comptes triés du plus froid au plus chaud', async () => {
    mount()
    await waitFor(() => expect(screen.getByText('Compte froid')).toBeInTheDocument())
    expect(screen.getByText('Compte tiède')).toBeInTheDocument()
    expect(crmApi.getMonPortefeuille).toHaveBeenCalled()
  })

  it('affiche un état vide quand le portefeuille est vide', async () => {
    crmApi.getMonPortefeuille.mockResolvedValueOnce({ data: { count: 0, results: [] } })
    mount()
    await waitFor(() => expect(
      screen.getByText(/Aucun compte dans votre portefeuille/),
    ).toBeInTheDocument())
  })
})
