import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* WIR193 — `ComptageScanPanel` (XSTK5) était construit et testé mais monté
   NULLE PART. Ce test garantit qu'il est ATTEIGNABLE depuis l'écran routé
   `/logistique/comptages` : sélectionner une session → bouton « Scan ». */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const SESSION = {
  id: 12,
  reference: 'CYC-202607-0002',
  statut: 'en_cours',
  classe_abc: 'toutes',
  lignes: [
    {
      id: 90, produit: 5, produit_nom: 'Onduleur 5kW', designation: 'Onduleur 5kW',
      quantite_theorique: 4, quantite_comptee: null, compte: false, ecart: 0,
    },
  ],
}

vi.mock('../../api/stockApi', () => ({
  default: {
    resolveCode: vi.fn(),
    getProduits: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
}))
vi.mock('../../api/installationsApi', () => ({
  default: {
    getSessionsComptage: vi.fn(() => Promise.resolve({ data: [SESSION] })),
    getSessionComptage: vi.fn(() => Promise.resolve({ data: SESSION })),
    updateComptageLigne: vi.fn(() => Promise.resolve({ data: SESSION.lignes[0] })),
    ajouterLigneComptage: vi.fn(() => Promise.resolve({ data: SESSION.lignes[0] })),
    createSessionComptage: vi.fn(() => Promise.resolve({ data: SESSION })),
    demarrerComptage: vi.fn(() => Promise.resolve({ data: SESSION })),
    terminerComptage: vi.fn(() => Promise.resolve({ data: SESSION })),
  },
}))

import installationsApi from '../../api/installationsApi'
import ComptageCyclesScreen from './ComptageCyclesScreen'

beforeEach(() => { vi.clearAllMocks() })

describe('ComptageCyclesScreen — WIR193 bouton Scan', () => {
  it('monte ComptageScanPanel sur la session sélectionnée', async () => {
    const user = userEvent.setup()
    render(<ComptageCyclesScreen />)

    await user.click(await screen.findByText('CYC-202607-0002'))

    // Vue « Saisie » par défaut : aucune barre de scan.
    expect(screen.queryByLabelText('Code scanné ou saisi manuellement')).toBeNull()

    await user.click(screen.getByRole('button', { name: 'Scan' }))

    await waitFor(() => expect(installationsApi.getSessionComptage).toHaveBeenCalledWith(12))
    expect(
      await screen.findByLabelText('Code scanné ou saisi manuellement'),
    ).toBeInTheDocument()
  })
})
