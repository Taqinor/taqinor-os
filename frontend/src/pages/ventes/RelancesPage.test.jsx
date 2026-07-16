import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

const ROWS = [
  {
    id: 1, reference: 'FAC-001', client_id: 42, client_nom: 'ACME SARL',
    montant_du: 1000, niveau: null,
  },
  {
    id: 2, reference: 'FAC-002', client_id: 99, client_nom: 'Globex',
    montant_du: 2000, niveau: null,
  },
]

vi.mock('../../api/ventesApi', () => ({
  default: {
    getRelances: vi.fn(() => Promise.resolve({ data: ROWS })),
  },
}))

import RelancesPage from './RelancesPage'

/* VX112 — la page /ventes/relances lit ?client=<id> (posé par le drill-down
   de la balance âgée) et pré-filtre la liste sur ce client, sans appel API
   supplémentaire (filtrage d'affichage, miroir du niveauFilter existant). */
describe('RelancesPage (VX112 — pré-filtre client via ?client=)', () => {
  it('sans ?client=, affiche toutes les factures', async () => {
    render(
      <MemoryRouter initialEntries={['/ventes/relances']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.getByText('Globex')).toBeInTheDocument()
  })

  it('avec ?client=42, ne montre que les factures de ce client', async () => {
    render(
      <MemoryRouter initialEntries={['/ventes/relances?client=42']}>
        <RelancesPage />
      </MemoryRouter>,
    )
    expect(await screen.findByText('ACME SARL')).toBeInTheDocument()
    expect(screen.queryByText('Globex')).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: /effacer/ })).toHaveAttribute('href', '/ventes/relances')
  })
})
