// QP2 — renommer une ligne de devis est réservé à Directeur + Commercial
// responsable ; les autres rôles ont la désignation en LECTURE SEULE. Un rôle
// autorisé qui renomme une ligne à l'écart du nom du produit reçoit le choix
// « renommer ici seulement » vs « créer un nouveau produit dans le stock »
// (clone serveur via stockApi.dupliquerProduit — prix d'achat côté serveur).

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

// APIs mockées (aucun appel réseau réel au montage).
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
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'

// Un catalogue minimal : le Smart Meter devient une ligne à produit lié dans la
// table par défaut (defaultProductLines), donc renommable.
const PRODUITS = [
  { id: 10, nom: 'Smart Meter Huawei DTSU666', prix_vente: 1500, tva: 20, is_archived: false, prix_achat: 900 },
]

function makeStore({ role_nom, permissions }) {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom, permissions,
        isAuthenticated: true, loading: false,
      },
    },
  })
}

function renderGenerator(authState) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: PRODUITS })
  return render(
    <Provider store={makeStore(authState)}>
      <MemoryRouter>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

// jsdom : shims requis par le générateur (scrollIntoView, matchMedia,
// ResizeObserver via recharts).
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
  if (!global.ResizeObserver) {
    global.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

// Trouve l'input de désignation du Smart Meter (ligne à produit lié).
async function findSmartMeterDesignation() {
  const input = await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
  return input
}

describe('QP2 — gate de renommage de ligne', () => {
  it('rôle non autorisé (Magasinier) : désignation en lecture seule', async () => {
    renderGenerator({ role_nom: 'Magasinier', permissions: [] })
    const input = await findSmartMeterDesignation()
    expect(input).toHaveAttribute('readonly')
    expect(input).toBeDisabled()
  })

  it('rôle autorisé (Directeur) : désignation éditable', async () => {
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    expect(input).not.toHaveAttribute('readonly')
    expect(input).not.toBeDisabled()
  })
})

describe('QP2 — renommer : deux options', () => {
  it('renommer + blur ouvre le dialogue à deux choix', async () => {
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    fireEvent.change(input, { target: { value: 'Smart Meter édition spéciale' } })
    fireEvent.blur(input)
    const dialog = await screen.findByRole('dialog')
    expect(within(dialog).getByRole('button', { name: /Renommer sur ce devis seulement/ })).toBeInTheDocument()
    expect(within(dialog).getByRole('button', { name: /Créer un nouveau produit/ })).toBeInTheDocument()
  })

  it('« renommer ici » garde le texte divergent, aucun produit créé', async () => {
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    fireEvent.change(input, { target: { value: 'Smart Meter renommé ici' } })
    fireEvent.blur(input)
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Renommer sur ce devis seulement/ }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(stockApi.dupliquerProduit).not.toHaveBeenCalled()
    expect(screen.getByDisplayValue('Smart Meter renommé ici')).toBeInTheDocument()
  })

  it('« créer un nouveau produit » clone via l\'API et relie la ligne au clone', async () => {
    stockApi.dupliquerProduit.mockResolvedValue({
      data: { id: 99, nom: 'Smart Meter clone', prix_vente: 1500, tva: 20, prix_achat: 900, is_archived: false },
    })
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    fireEvent.change(input, { target: { value: 'Smart Meter clone' } })
    fireEvent.blur(input)
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Créer un nouveau produit/ }))
    await waitFor(() => expect(stockApi.dupliquerProduit).toHaveBeenCalled())
    // produit lié = String(id) dans la table par défaut ('10').
    expect(stockApi.dupliquerProduit).toHaveBeenCalledWith('10', 'Smart Meter clone')
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(screen.getByDisplayValue('Smart Meter clone')).toBeInTheDocument()
  })
})
