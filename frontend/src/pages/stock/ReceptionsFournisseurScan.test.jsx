import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

/* WIR193 — `ReceptionScanPanel` (XSTK5) était construit et testé mais monté
   NULLE PART. Ce test garantit qu'il est ATTEIGNABLE depuis l'écran routé des
   réceptions fournisseur : bouton « Scan » → choix du BCF → panneau monté. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const BCF = {
  id: 1,
  reference: 'BCF-202607-0001',
  fournisseur_nom: 'SunRak',
  statut: 'envoye',
  est_entierement_recu: false,
  lignes: [
    { id: 11, produit: 5, produit_nom: 'Onduleur 5kW', quantite: 10, quantite_recue: 0 },
  ],
}

vi.mock('../../api/stockApi', () => ({
  default: {
    getReceptionsFournisseur: vi.fn(() => Promise.resolve({ data: [] })),
    getBonsCommandeFournisseur: vi.fn(() => Promise.resolve({ data: [BCF] })),
    getBonCommandeFournisseur: vi.fn(() => Promise.resolve({ data: BCF })),
    getReceptionFournisseur: vi.fn(() => Promise.resolve({ data: {} })),
    resolveCode: vi.fn(),
    recevoirBcf: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// ZSTK13 — `useStockFlags` lit le profil entreprise ; défaut True.
vi.mock('../../api/parametresApi', async (importOriginal) => {
  const actual = await importOriginal()
  return {
    ...actual,
    default: { ...actual.default, getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
  }
})

import stockApi from '../../api/stockApi'
import ReceptionsFournisseur from './ReceptionsFournisseur'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeEach(() => { vi.clearAllMocks() })

describe('ReceptionsFournisseur — WIR193 réception au scan', () => {
  it('ouvre la modale « Scan » et y monte ReceptionScanPanel sur le BCF choisi', async () => {
    const user = userEvent.setup()
    render(
      <MemoryRouter initialEntries={['/stock/receptions']}>
        <ThemeProvider><ReceptionsFournisseur /></ThemeProvider>
      </MemoryRouter>,
    )

    await waitFor(() => expect(stockApi.getBonsCommandeFournisseur).toHaveBeenCalled())

    // Rien de scannable tant que la modale n'est pas ouverte.
    expect(screen.queryByLabelText('Code scanné ou saisi manuellement')).toBeNull()

    const boutonScan = await screen.findByRole('button', { name: /Scan/ })
    await waitFor(() => expect(boutonScan).not.toBeDisabled())
    await user.click(boutonScan)

    // Un seul BCF recevable : il est présélectionné, le panneau se monte.
    await waitFor(() => expect(stockApi.getBonCommandeFournisseur).toHaveBeenCalledWith(1))
    expect(
      await screen.findByLabelText('Code scanné ou saisi manuellement'),
    ).toBeInTheDocument()
  })
})
