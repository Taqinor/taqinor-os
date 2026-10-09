import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* AFAC63 — « Total encaissé » est calculé sur TOUTES les pages de /paiements/
   (forme DRF réelle {count, next, results}, 50 par page) : 56 paiements
   encaissés dont 1 rejeté ⇒ le pied de tableau compte 55 et somme tout le
   monde sauf le rejeté. */

vi.mock('../../hooks/useHasPermission', () => ({
  useHasPermission: () => false,
  useHasRole: () => false,
  useIsAdmin: () => false,
  useIsAdminOrResponsable: () => false,
}))

const TOUS = Array.from({ length: 56 }, (_, i) => ({
  id: i + 1, montant: '10.00', mode: 'virement', mode_display: 'Virement',
  date_paiement: '2026-08-01', facture_reference: `FAC-${i + 1}`,
  client: 1, client_nom: 'ACME', statut: i === 55 ? 'rejete' : 'valide',
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getPaiements: vi.fn((params = {}) => {
      const page = params.page || 1
      const results = TOUS.slice((page - 1) * 50, page * 50)
      return Promise.resolve({
        data: { count: TOUS.length, next: page * 50 < TOUS.length ? 'x' : null, results },
      })
    }),
    importReleveDryRun: vi.fn(),
    importReleveCommit: vi.fn(),
    rejeterPaiement: vi.fn(),
  },
}))

import PaiementsPage from './PaiementsPage'

describe('PaiementsPage — AFAC63 : toutes les pages', () => {
  it('« Total encaissé (55) » sur les 56 paiements (le rejeté est exclu)', async () => {
    render(<MemoryRouter><PaiementsPage /></MemoryRouter>)
    expect(await screen.findByText(/Total encaissé \(55\)/)).toBeInTheDocument()
  })
})
