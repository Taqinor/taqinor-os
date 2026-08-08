import { describe, it, expect, vi, beforeEach, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* PACT102 — Partenaires : agréer un partenaire, qualifier une soumission
   (fait apparaître le lead RÉEL créé par le serveur, jamais un lead
   fictif), régler une commission. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const {
  getPartenaires, createPartenaire, activerPartenaire,
  getSoumissions, qualifierSoumission, getCommissions, marquerPayee,
} = vi.hoisted(() => ({
  getPartenaires: vi.fn(),
  createPartenaire: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  activerPartenaire: vi.fn(() => Promise.resolve({ data: {} })),
  getSoumissions: vi.fn(),
  qualifierSoumission: vi.fn(),
  getCommissions: vi.fn(),
  marquerPayee: vi.fn(),
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getPartenaires: (...args) => getPartenaires(...args),
    createPartenaire: (...args) => createPartenaire(...args),
    activerPartenaire: (...args) => activerPartenaire(...args),
    getSoumissionsLeadPartenaire: (...args) => getSoumissions(...args),
    qualifierSoumissionLeadPartenaire: (...args) => qualifierSoumission(...args),
    getCommissionsPartenaire: (...args) => getCommissions(...args),
    marquerPayeeCommissionPartenaire: (...args) => marquerPayee(...args),
    getReleveCommissionsPartenaire: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

import Partenaires from './Partenaires'

beforeEach(() => {
  vi.clearAllMocks()
  getPartenaires.mockResolvedValue({
    data: [
      {
        id: 1, nom: 'SolarZen SARL', type_partenaire: 'apporteur',
        taux_commission: '5.00', statut_onboarding: 'prospect',
      },
    ],
  })
  getSoumissions.mockResolvedValue({
    data: [
      { id: 10, partenaire: 1, nom_prospect: 'Ali Ben', ville: 'Marrakech', statut: 'soumis', lead_id: null },
    ],
  })
  getCommissions.mockResolvedValue({
    data: [
      { id: 20, partenaire: 1, base_ht: '10000.00', taux: '5.00', montant: '500.00', statut: 'due' },
    ],
  })
})

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('Partenaires (PACT102)', () => {
  it('affiche les partenaires existants', async () => {
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))
  })

  it('crée un partenaire', async () => {
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.type(screen.getByLabelText('Nom du partenaire'), 'Green Watt')
    await user.click(screen.getByRole('button', { name: 'Créer le partenaire' }))

    await waitFor(() => expect(createPartenaire).toHaveBeenCalledWith(expect.objectContaining({
      nom: 'Green Watt', type_partenaire: 'apporteur',
    })))
  })

  it('agrée un partenaire prospect', async () => {
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(await screen.findByRole('button', { name: 'Agréer ce partenaire' }))

    await waitFor(() => expect(activerPartenaire).toHaveBeenCalledWith(1))
  })

  it('qualifie une soumission et affiche le lead réel créé par le serveur', async () => {
    qualifierSoumission.mockResolvedValue({
      data: { id: 10, partenaire: 1, nom_prospect: 'Ali Ben', statut: 'qualifie', lead_id: 77 },
    })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(await screen.findByRole('button', { name: 'Qualifier' }))

    await waitFor(() => expect(qualifierSoumission).toHaveBeenCalledWith(10))
    expect(await screen.findByText(/lead #77/)).toBeInTheDocument()
  })

  it('règle une commission due', async () => {
    marquerPayee.mockResolvedValue({
      data: { id: 20, partenaire: 1, base_ht: '10000.00', taux: '5.00', montant: '500.00', statut: 'payee' },
    })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Détails' }))
    await user.click(await screen.findByRole('button', { name: 'Marquer payée' }))

    await waitFor(() => expect(marquerPayee).toHaveBeenCalledWith(20))
  })
})
