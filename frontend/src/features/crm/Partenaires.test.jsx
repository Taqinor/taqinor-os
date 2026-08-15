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
  createCommission, getReleve,
} = vi.hoisted(() => ({
  getPartenaires: vi.fn(),
  createPartenaire: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
  activerPartenaire: vi.fn(() => Promise.resolve({ data: {} })),
  getSoumissions: vi.fn(),
  qualifierSoumission: vi.fn(),
  getCommissions: vi.fn(),
  marquerPayee: vi.fn(),
  createCommission: vi.fn(() => Promise.resolve({ data: { id: 21 } })),
  getReleve: vi.fn(() => Promise.resolve({ data: [] })),
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
    createCommissionPartenaire: (...args) => createCommission(...args),
    getReleveCommissionsPartenaire: (...args) => getReleve(...args),
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
    await user.click(screen.getAllByRole('button', { name: 'Créer le partenaire' })[0])

    await waitFor(() => expect(createPartenaire).toHaveBeenCalledWith(expect.objectContaining({
      nom: 'Green Watt', type_partenaire: 'apporteur',
    })))
  })

  it('agrée un partenaire prospect', async () => {
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.click((await screen.findAllByRole('button', { name: 'Agréer ce partenaire' }))[0])

    await waitFor(() => expect(activerPartenaire).toHaveBeenCalledWith(1))
  })

  it('qualifie une soumission et affiche le lead réel créé par le serveur', async () => {
    qualifierSoumission.mockResolvedValue({
      data: { id: 10, partenaire: 1, nom_prospect: 'Ali Ben', statut: 'qualifie', lead_id: 77 },
    })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.click((await screen.findAllByRole('button', { name: 'Qualifier' }))[0])

    await waitFor(() => expect(qualifierSoumission).toHaveBeenCalledWith(10))
    expect((await screen.findAllByText(/lead #77/)).length).toBeGreaterThan(0)
  })

  it('règle une commission due', async () => {
    marquerPayee.mockResolvedValue({
      data: { id: 20, partenaire: 1, base_ht: '10000.00', taux: '5.00', montant: '500.00', statut: 'payee' },
    })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await user.click((await screen.findAllByRole('button', { name: 'Marquer payée' }))[0])

    await waitFor(() => expect(marquerPayee).toHaveBeenCalledWith(20))
  })

  // WIR228 — le tableau des commissions n'avait aucun chemin de création :
  // `createCommissionPartenaire` existait côté API mais aucun formulaire ne
  // l'appelait.
  it('crée une commission pour le partenaire sélectionné puis elle apparaît', async () => {
    getCommissions
      .mockResolvedValueOnce({
        data: [{ id: 20, partenaire: 1, base_ht: '10000.00', taux: '5.00', montant: '500.00', statut: 'due' }],
      })
      .mockResolvedValueOnce({
        data: [
          { id: 20, partenaire: 1, base_ht: '10000.00', taux: '5.00', montant: '500.00', statut: 'due' },
          { id: 21, partenaire: 1, base_ht: '8000.00', taux: '5.00', montant: '400.00', statut: 'due' },
        ],
      })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getAllByRole('button', { name: 'Détails' })[0])
    await screen.findAllByRole('button', { name: 'Agréer ce partenaire' })

    await user.type(screen.getByLabelText('Base HT de la commission'), '8000')
    await user.click(screen.getByRole('button', { name: 'Créer la commission' }))

    await waitFor(() => expect(createCommission).toHaveBeenCalledWith(expect.objectContaining({
      partenaire: 1, base_ht: '8000',
    })))
    expect((await screen.findAllByText('400.00')).length).toBeGreaterThan(0)
  })

  // WIR228 — le relevé (dû/payé/total par partenaire) n'avait aucun bouton
  // pour l'afficher, bien que l'appel API existait déjà.
  it('affiche le relevé dû/payé/total par partenaire', async () => {
    getReleve.mockResolvedValueOnce({
      data: [{ partenaire: 1, nom: 'SolarZen SARL', due: 500, payee: 1200, total: 1700 }],
    })
    const user = userEvent.setup()
    withProviders(<Partenaires />)
    await waitFor(() => expect(screen.getAllByText('SolarZen SARL').length).toBeGreaterThan(0))

    await user.click(screen.getByRole('button', { name: 'Relevé' }))

    await waitFor(() => expect(getReleve).toHaveBeenCalled())
    expect(await screen.findByText('1700')).toBeInTheDocument()
  })
})
