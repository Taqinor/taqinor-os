// QP2 — renommer une ligne de devis est réservé à Directeur + Commercial
// responsable ; les autres rôles ont la désignation en LECTURE SEULE. Un rôle
// autorisé qui renomme une ligne à l'écart du nom du produit reçoit le choix
// « renommer ici seulement » vs « créer un nouveau produit dans le stock »
// (clone serveur via stockApi.dupliquerProduit — prix d'achat côté serveur).

import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor, within } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

// APIs mockées (aucun appel réseau réel au montage).
vi.mock('../../api/crmApi', async () => (await import('../../test/mocksApiDevis.js')).crmApiMock())
vi.mock('../../api/stockApi', async () => (await import('../../test/mocksApiDevis.js')).stockApiDuplication())
vi.mock('../../api/parametresApi', async () => (await import('../../test/mocksApiDevis.js')).parametresApiMock())
vi.mock('../../api/ventesApi', async () => (await import('../../test/mocksApiDevis.js')).ventesApiMock({
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import DevisGenerator from './DevisGenerator'
import { declarerBeforeEachDevis } from './devisGenerator.testHelpers.jsx'

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
declarerBeforeEachDevis({ stockApi, crmApi })

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

// T4-X4-015 — le choix du dialogue CONTINUE l'enregistrement qu'il a interrompu :
// le blur de la désignation (mousedown sur « Créer ») ouvre la fenêtre et avale le clic.
describe('T4-X4-015 — le choix poursuit l\'enregistrement interrompu', () => {
  const ouvrirDepuisCreer = async () => {
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    const soumis = vi.fn((e) => e.preventDefault())
    document.getElementById('gen-form').addEventListener('submit', soumis)
    const creer = screen.getAllByRole('button', { name: /Créer le devis/ })[0]
    expect(creer).toHaveAttribute('type', 'submit')
    fireEvent.change(input, { target: { value: 'Smart Meter renommé ici' } })
    fireEvent.blur(input, { relatedTarget: creer })
    const dialog = await screen.findByRole('dialog')
    return { dialog, soumis }
  }

  it('« Renommer sur ce devis seulement » enregistre ensuite le devis', async () => {
    const { dialog, soumis } = await ouvrirDepuisCreer()
    fireEvent.click(within(dialog).getByRole('button', { name: /Renommer sur ce devis seulement/ }))
    await waitFor(() => expect(soumis).toHaveBeenCalledTimes(1))
  })

  it('« Créer un nouveau produit » enregistre ensuite le devis', async () => {
    stockApi.dupliquerProduit.mockResolvedValue({
      data: { id: 99, nom: 'Smart Meter renommé ici', prix_vente: 1500, tva: 20, prix_achat: 900, is_archived: false },
    })
    const { dialog, soumis } = await ouvrirDepuisCreer()
    fireEvent.click(within(dialog).getByRole('button', { name: /Créer un nouveau produit/ }))
    await waitFor(() => expect(soumis).toHaveBeenCalledTimes(1))
  })

  it('une désignation quittée autrement (Tab) ne déclenche aucun enregistrement', async () => {
    renderGenerator({ role_nom: 'Directeur', permissions: ['stock_creer'] })
    const input = await findSmartMeterDesignation()
    const soumis = vi.fn((e) => e.preventDefault())
    document.getElementById('gen-form').addEventListener('submit', soumis)
    fireEvent.change(input, { target: { value: 'Smart Meter autre' } })
    fireEvent.blur(input)
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Renommer sur ce devis seulement/ }))
    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull())
    expect(soumis).not.toHaveBeenCalled()
  })
})
