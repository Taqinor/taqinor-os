// XSAL3 — au choix d'un produit (et à chaque changement de quantité/client),
// le générateur interroge `getPrixApplicable` (résolution liste client +
// paliers XSAL1-2) et affiche un badge « Tarif : <liste> » quand une liste de
// prix négociée s'applique (source !== 'standard'). Prix pré-rempli depuis la
// résolution, jamais un blocage/snap de la saisie manuelle ultérieure.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

// ══ QXMT — raccordement MOYENNE TENSION dans l'étude industrielle ════════════
// Un dossier > 50 kW est raccordé en MT et n'est PAS facturé au barème BT :
// l'étude bascule sur le barème ONEE « Tarif Général (MT) » pondéré par la
// répartition horaire du site. Sans cette répartition (les plages MT
// officielles ne sont pas publiées), les économies sont OMISES — jamais
// remplacées par un chiffre supposé.

/** Amène l'écran en mode Industriel avec une puissance et une conso saisies. */
async function setupIndustriel() {
  renderGenerator()
  await screen.findByDisplayValue('Smart Meter Huawei DTSU666')
  fireEvent.click(screen.getByRole('radio', { name: /Industriel/ }))
  // `Consommation mensuelle` n'existe QUE en industriel/commercial : l'attendre
  // prouve que la bascule de marché a bien eu lieu avant la suite.
  fireEvent.change(await screen.findByLabelText(/Consommation mensuelle/), {
    target: { value: '20000' },
  })
  fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), {
    target: { value: '100' },
  })
}

describe('QXMT — étude industrielle en moyenne tension', () => {
  it('BT (défaut) : aucun bloc MT, étude chiffrée comme avant', async () => {
    await setupIndustriel()
    expect(screen.queryByTestId('gen-mt-block')).not.toBeInTheDocument()
    expect(await screen.findByText(/Économies annuelles/)).toBeInTheDocument()
    expect(screen.queryByTestId('etude-mt-motif')).not.toBeInTheDocument()
  })

  it('MT sans répartition horaire : économies OMISES + motif explicite', async () => {
    await setupIndustriel()
    fireEvent.click(screen.getByRole('radio', { name: /Moyenne tension/ }))
    expect(await screen.findByTestId('gen-mt-block')).toBeInTheDocument()
    // le motif est affiché, la carte « Économies » disparaît (pas de « 0 »)
    expect(await screen.findByTestId('etude-mt-motif')).toBeInTheDocument()
    expect(screen.queryByText(/Économies annuelles/)).not.toBeInTheDocument()
    expect(screen.getByTestId('gen-mt-manquant')).toBeInTheDocument()
  })

  it('MT avec répartition : tarif MT sourcé affiché et économies rétablies', async () => {
    await setupIndustriel()
    fireEvent.click(screen.getByRole('radio', { name: /Moyenne tension/ }))
    await screen.findByTestId('gen-mt-block')
    fireEvent.change(screen.getByTestId('gen-mt-pointe'), { target: { value: '20' } })
    fireEvent.change(screen.getByTestId('gen-mt-pleines'), { target: { value: '40' } })
    fireEvent.change(screen.getByTestId('gen-mt-creuses'), { target: { value: '40' } })
    // 0,2×1,4157 + 0,4×1,0101 + 0,4×0,7398 = 0,9831 DH/kWh
    expect(await screen.findByTestId('gen-mt-tarif')).toHaveTextContent('0,9831')
    // la source voyage TOUJOURS avec le chiffre
    expect(await screen.findByTestId('etude-mt-source')).toHaveTextContent('one.org.ma')
    expect(await screen.findByText(/Économies annuelles/)).toBeInTheDocument()
    expect(screen.queryByTestId('etude-mt-motif')).not.toBeInTheDocument()
  })

  it('les champs MT n\'imposent aucune contrainte de saisie (step any, pas de max)', async () => {
    await setupIndustriel()
    fireEvent.click(screen.getByRole('radio', { name: /Moyenne tension/ }))
    for (const key of ['pointe', 'pleines', 'creuses']) {
      const input = await screen.findByTestId(`gen-mt-${key}`)
      expect(input).toHaveAttribute('step', 'any')
      expect(input).not.toHaveAttribute('max')
      // une décimale libre est conservée telle quelle — jamais arrondie
      fireEvent.change(input, { target: { value: '33.333' } })
      expect(input).toHaveValue(33.333)
    }
  })
})
