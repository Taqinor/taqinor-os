// XSAL3 — au choix d'un produit (et à chaque changement de quantité/client),
// le générateur interroge `getPrixApplicable` (résolution liste client +
// paliers XSAL1-2) et affiche un badge « Tarif : <liste> » quand une liste de
// prix négociée s'applique (source !== 'standard'). Prix pré-rempli depuis la
// résolution, jamais un blocage/snap de la saisie manuelle ultérieure.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: {
    getProduits: vi.fn(() => Promise.resolve({ data: [] })),
    dupliquerProduit: vi.fn(),
  },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PRODUITS = [
  { id: 10, nom: 'Smart Meter Huawei DTSU666', prix_vente: 1500, tva: 20, is_archived: false, prix_achat: 900 },
]

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: ['stock_creer'],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderGenerator() {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  if (!Element.prototype.scrollIntoView) Element.prototype.scrollIntoView = () => {}
  if (!window.matchMedia) {
    window.matchMedia = vi.fn().mockImplementation((q) => ({
      matches: false, media: q, onchange: null,
      addListener: vi.fn(), removeListener: vi.fn(),
      addEventListener: vi.fn(), removeEventListener: vi.fn(), dispatchEvent: vi.fn(),
    }))
  }
  if (!globalThis.ResizeObserver) {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

describe('XSAL3 — badge tarif applicable', () => {
  it('affiche « Tarif : <liste> » quand la résolution renvoie une liste', async () => {
    ventesApi.getPrixApplicable.mockResolvedValue({
      data: { produit: 10, quantite: '1', prix: '1350.00', source: 'liste', liste_nom: 'Revendeur' },
    })
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    await waitFor(() => expect(ventesApi.getPrixApplicable).toHaveBeenCalled())
    expect(await screen.findByText(/Tarif : Revendeur/)).toBeInTheDocument()
  })

  it("n'affiche aucun badge quand la source est « standard »", async () => {
    ventesApi.getPrixApplicable.mockResolvedValue({
      data: { produit: 10, quantite: '1', prix: '1500.00', source: 'standard', liste_nom: null },
    })
    renderGenerator()
    await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
    await waitFor(() => expect(ventesApi.getPrixApplicable).toHaveBeenCalled())
    expect(screen.queryByText(/Tarif :/)).not.toBeInTheDocument()
  })
})
