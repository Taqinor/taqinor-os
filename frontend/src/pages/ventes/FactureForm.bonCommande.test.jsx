// AFAC67 — FactureForm ne recopie plus le devis en JS : un BC issu d'un devis se
// facture par `creer-facture` (porte unique) ; un BC déjà facturé n'est plus proposé.
// Run : npx vitest run src/pages/ventes/FactureForm.bonCommande.test.jsx
import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
  Element.prototype.hasPointerCapture ??= () => false
  Element.prototype.setPointerCapture ??= () => {}
  Element.prototype.releasePointerCapture ??= () => {}
  Element.prototype.scrollIntoView ??= () => {}
})

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({ data: { count: 1, next: null, results: [{ id: 5, nom: 'ACME' }] } })),
    post: vi.fn(), patch: vi.fn(), put: vi.fn(), delete: vi.fn(),
  },
}))

// Formes réelles : BonCommandeSerializer (devis, devis_reference, facture_active).
const BC_DEVIS = { id: 11, reference: 'BC-0011', client: 5, client_nom: 'ACME', devis: 3, devis_reference: 'DEV-0003', facture_active: false }
const BC_FACTURE = { id: 12, reference: 'BC-0012', client: 5, client_nom: 'ACME', devis: 4, devis_reference: 'DEV-0004', facture_active: true }
const BC_LIBRE = { id: 13, reference: 'BC-0013', client: 5, client_nom: 'ACME', devis: null, facture_active: false }

const apis = vi.hoisted(() => ({
  ventes: {
    getBonsCommande: vi.fn(),
    getFacture: vi.fn(() => Promise.resolve({ data: {} })),
    getDevisById: vi.fn(),
    creerFactureBC: vi.fn(),
  },
  stock: { getProduits: vi.fn(() => Promise.resolve({ data: { results: [], next: null } })) },
}))
vi.mock('../../api/ventesApi', () => ({ default: apis.ventes }))
vi.mock('../../api/stockApi', () => ({ default: apis.stock }))

import ventesReducer from '../../features/ventes/store/ventesSlice'
import authReducer from '../../features/auth/store/authSlice'
import FactureForm from './FactureForm'

const AUTH = { user: { id: 1 }, role: 'responsable', permissions: [], isAuthenticated: true, loading: false }
const rendre = (onSaved = () => {}) => render(
  <Provider store={configureStore({ reducer: { auth: authReducer, ventes: ventesReducer }, preloadedState: { auth: AUTH } })}>
    <FactureForm onClose={() => {}} onSaved={onSaved} />
  </Provider>,
)

beforeEach(() => {
  vi.clearAllMocks()
  apis.ventes.getBonsCommande.mockResolvedValue({
    data: { count: 3, next: null, results: [BC_DEVIS, BC_FACTURE, BC_LIBRE] },
  })
})

const ouvrirSelecteur = async (user) => {
  await waitFor(() => expect(apis.ventes.getBonsCommande).toHaveBeenCalled())
  await user.click(document.getElementById('fc-bc'))
}

describe('AFAC67 — FactureForm : BC issu d\'un devis', () => {
  it('le BC déjà facturé n\'est pas proposé', async () => {
    const user = userEvent.setup()
    rendre()
    await ouvrirSelecteur(user)
    expect(await screen.findByRole('option', { name: /BC-0011/ })).toBeInTheDocument()
    expect(screen.queryByRole('option', { name: /BC-0012/ })).toBeNull()
  })

  it('choisir le BC du devis : aucune ligne recopiée, facture créée par creer-facture', async () => {
    apis.ventes.creerFactureBC.mockResolvedValue({
      data: { id: 90, reference: 'FAC-2026-10-0090', montant_ttc: '10800.00' },
    })
    const onSaved = vi.fn()
    const user = userEvent.setup()
    rendre(onSaved)
    await ouvrirSelecteur(user)
    await user.click(await screen.findByRole('option', { name: /BC-0011/ }))

    // Plus aucune recopie JS du devis.
    expect(apis.ventes.getDevisById).not.toHaveBeenCalled()
    expect(screen.queryByLabelText(/Désignation/)).toBeNull()

    await user.click(await screen.findByRole('button', { name: /Créer la facture depuis ce BC/ }))
    await waitFor(() => expect(apis.ventes.creerFactureBC).toHaveBeenCalledWith(11))
    const statut = await screen.findByRole('status')
    expect(statut).toHaveTextContent('FAC-2026-10-0090')
    expect(statut).toHaveTextContent(/10\s?800,00/)
    expect(onSaved).toHaveBeenCalled()
  })

  it('un BC sans devis garde le formulaire libre', async () => {
    const user = userEvent.setup()
    rendre()
    await ouvrirSelecteur(user)
    await user.click(await screen.findByRole('option', { name: /BC-0013/ }))
    expect(screen.queryByRole('button', { name: /Créer la facture depuis ce BC/ })).toBeNull()
    expect(screen.getByRole('button', { name: 'Créer la facture' })).not.toBeDisabled()
  })
})
