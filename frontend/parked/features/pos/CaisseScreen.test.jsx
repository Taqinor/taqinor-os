import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* WIR58 — encaisser une facture/devis existant au comptoir (XPOS6).
   Les wrappers posApi.rechercheFactures/encaisserFacture existaient sans aucun
   appelant : on vérifie ici le flux complet recherche → sélection → montant →
   encaissement depuis la caisse. Réseau mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const { rechercheFactures, encaisserFacture } = vi.hoisted(() => ({
  rechercheFactures: vi.fn(() => Promise.resolve({
    data: [
      { id: 7, reference: 'FA-2026-0007', client: 'ACME SARL', montant_du: '1200', total_ttc: '1200' },
    ],
  })),
  encaisserFacture: vi.fn(() => Promise.resolve({
    data: { id: 42, montant: '1200', mode: 'especes', facture: 'FA-2026-0007' },
  })),
}))

vi.mock('../../api/posApi', () => ({
  default: {
    getProduits: () => Promise.resolve({ data: [] }),
    searchClients: () => Promise.resolve({ data: [] }),
    rechercheFactures: (...a) => rechercheFactures(...a),
    encaisserFacture: (...a) => encaisserFacture(...a),
  },
}))

vi.mock('../../api/axios', () => ({ default: { defaults: { baseURL: '' } } }))

import CaisseScreen from './CaisseScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('CaisseScreen — encaisser une facture existante (WIR58)', () => {
  it('recherche, sélectionne et encaisse une facture existante', async () => {
    withProviders(<CaisseScreen />)

    fireEvent.click(screen.getByRole('button', { name: 'Encaisser une facture existante' }))
    await waitFor(() => expect(screen.getByLabelText('Référence ou client')).toBeTruthy())

    fireEvent.change(screen.getByLabelText('Référence ou client'), { target: { value: 'ACME' } })
    fireEvent.click(screen.getByRole('button', { name: 'Rechercher' }))

    await waitFor(() => expect(rechercheFactures).toHaveBeenCalledWith('ACME'))
    await waitFor(() => expect(screen.getByText('FA-2026-0007')).toBeTruthy())

    fireEvent.click(screen.getByText('FA-2026-0007'))

    // le montant est pré-rempli avec le solde dû
    await waitFor(() => expect(screen.getByLabelText('Montant à encaisser').value).toBe('1200'))

    fireEvent.click(screen.getByRole('button', { name: 'Encaisser la facture' }))

    await waitFor(() => expect(encaisserFacture).toHaveBeenCalledWith({
      facture: 7,
      montant: '1200',
      mode: 'especes',
    }))
  })
})
