import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

vi.mock('../../api/ventesApi', () => ({
  default: {
    getBalanceAgee: vi.fn(() => Promise.resolve({
      data: [
        {
          client_id: 42, client_nom: 'ACME SARL',
          b0_30: 1000, b31_60: 0, b61_90: 0, b90_plus: 0, total: 1000,
        },
      ],
    })),
    getClientRelevePdf: vi.fn(() => Promise.resolve({ data: new Blob() })),
  },
}))
vi.mock('../../api/reportingApi', () => ({
  default: { balanceAgeeXlsx: vi.fn() },
}))

import BalanceAgeePage from './BalanceAgeePage'

/* VX112 — drill-down « Relancer » depuis la balance âgée vers les relances
   filtrées sur le client (?client=<id>), miroir du ?produit= de
   MouvementsPage. Le PDF « Relevé » reste intact (2ᵉ action de ligne). */
describe('BalanceAgeePage (VX112 — drill-down Relancer)', () => {
  it('affiche un lien « Relancer » vers /ventes/relances?client=<id> et garde le bouton Relevé', async () => {
    render(
      <MemoryRouter>
        <BalanceAgeePage />
      </MemoryRouter>,
    )

    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()

    const relancerLink = screen.getByRole('link', { name: /Relancer/ })
    expect(relancerLink).toHaveAttribute('href', '/ventes/relances?client=42')

    expect(screen.getByRole('button', { name: /Relevé/ })).toBeInTheDocument()
  })
})
