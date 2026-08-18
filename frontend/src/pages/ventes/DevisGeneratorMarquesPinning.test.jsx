// PVMRQ (fondateur 18/08/2026) — le générateur charge les réglages « Gammes &
// marques » (`ventesApi.getParametresGammes`, gamme Essentielle par défaut —
// aucune gamme n'est encore portée par un devis NEUF) et les applique à
// l'auto-remplissage : une marque épinglée sans AUCUN produit correspondant
// en stock affiche le bandeau dédié, EXACT même patron visuel que
// `errors.autofill` (« Aucun produit du stock ne correspond à… »), et ne
// retombe JAMAIS sur une autre marque déjà en stock.
//
// AVERTISSEMENT — vitest ne peut pas s'exécuter dans cet environnement (la
// jonction node_modules est vide) : ce fichier suit exactement le patron de
// DevisGeneratorTarif.test.jsx (rendu réel, mocks des couches api) mais n'a
// PAS été exécuté ici — seule la vérification de syntaxe (esbuild) l'a été.

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
    getPrixApplicable: vi.fn(() => Promise.resolve({
      data: { source: 'standard' },
    })),
    // PVMRQ — réglage « Gammes & marques » : Jinko épinglé pour les panneaux,
    // absent du catalogue de test ci-dessous (voir PRODUITS).
    getParametresGammes: vi.fn(() => Promise.resolve({
      data: {
        id: 1,
        deux_gammes: false,
        nom_essentielle: 'Essentielle',
        nom_premium: 'Premium',
        marques: { Essentielle: { panneau: 'Jinko' }, Premium: {} },
      },
    })),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

// Catalogue solaire complet — SAUF un panneau Jinko : la seule marque de
// panneau en stock est Canadian Solar, jamais épinglée.
const PRODUITS = [
  { id: 1, nom: 'Onduleur réseau Huawei 10kW Triphasé', prix_vente: 16666.67, tva: 20, is_archived: false },
  { id: 2, nom: 'Panneau Canadien Solar 710W', prix_vente: 1166.67, tva: 10, is_archived: false, marque: 'Canadian Solar' },
  { id: 3, nom: 'Structures acier', prix_vente: 416.67, tva: 20, is_archived: false },
  { id: 4, nom: 'Socles', prix_vente: 66.67, tva: 20, is_archived: false },
  { id: 5, nom: 'Accessoires', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 6, nom: 'Tableau De Protection AC/DC', prix_vente: 1666.67, tva: 20, is_archived: false },
  { id: 7, nom: 'Installation', prix_vente: 4000, tva: 20, is_archived: false },
  { id: 8, nom: 'Transport', prix_vente: 833.33, tva: 20, is_archived: false },
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

describe('PVMRQ — marque de panneau épinglée introuvable au stock', () => {
  it('charge le réglage « Gammes & marques » au montage', async () => {
    renderGenerator()
    await waitFor(() => expect(ventesApi.getParametresGammes).toHaveBeenCalled())
  })

  it('bandeau « Marque épinglée introuvable » à l\'auto-remplissage, JAMAIS un repli sur Canadian Solar', async () => {
    renderGenerator()
    // Rendu réel une fois le stock chargé — même patron que
    // DevisGeneratorTarif.test.jsx/DevisGeneratorLinesInput.test.jsx : on
    // attend un produit TOUJOURS pré-rempli par `defaultProductLines` au
    // montage (ici « Installation », seul candidat du rôle dans PRODUITS ;
    // « Onduleur réseau » y reste un simple PLACEHOLDER — jamais choisi au
    // montage, voir solar.js `defaultProductLines` — donc n'est PAS un anchor
    // valable avant le clic Auto-remplir).
    await screen.findByDisplayValue('Installation')
    await waitFor(() => expect(ventesApi.getParametresGammes).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: /Auto-remplir depuis le stock/i }))

    expect(await screen.findByText(
      /Marque épinglée introuvable au stock : Jinko \(Panneaux\)/,
    )).toBeInTheDocument()
    expect(screen.getByText(/Paramètres → Gammes/)).toBeInTheDocument()
    // Jamais de repli silencieux sur le panneau Canadian Solar pourtant en stock.
    expect(screen.queryByDisplayValue('Panneau Canadien Solar 710W')).not.toBeInTheDocument()
    // La marque manquante n'ampute QUE le rôle panneau (seul rôle épinglé dans
    // ce réglage) : l'onduleur réseau, sans marque épinglée, reste
    // auto-rempli normalement avec le seul onduleur du stock.
    expect(await screen.findByDisplayValue(/Onduleur réseau Huawei/)).toBeInTheDocument()
  })

  it('sans réglage « Gammes & marques » accessible (403/erreur) : comportement historique, aucun bandeau', async () => {
    ventesApi.getParametresGammes.mockRejectedValueOnce({ response: { status: 403 } })
    renderGenerator()
    await screen.findByDisplayValue('Installation')
    await waitFor(() => expect(ventesApi.getParametresGammes).toHaveBeenCalled())

    fireEvent.change(screen.getByLabelText(/Nombre de panneaux/), { target: { value: '14' } })
    fireEvent.click(screen.getByRole('button', { name: /Auto-remplir depuis le stock/i }))

    // Le panneau Canadian Solar (seul en stock) est retenu normalement — pas
    // de préférence appliquée quand le réglage est indisponible.
    expect(await screen.findByDisplayValue('Panneau Canadien Solar 710W')).toBeInTheDocument()
    expect(screen.queryByText(/Marque épinglée introuvable/)).not.toBeInTheDocument()
  })
})
