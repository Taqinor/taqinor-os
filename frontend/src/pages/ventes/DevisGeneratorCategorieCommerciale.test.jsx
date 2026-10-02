// QJR575 — le défaut « Non précisée » de la catégorie commerciale se persiste
// null : un devis commercial sans categorie_commerciale, rouvert puis
// enregistré, renvoie `categorie_commerciale: null` (jamais la sentinelle).
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorCategorieCommerciale.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(() => Promise.resolve({ data: null })),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn() },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
  },
}))

import stockApi from '../../api/stockApi'
import parametresApi from '../../api/parametresApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = { id: 201, nom: 'Panneau Mono 550W', prix_vente: 1000, tva: 10, is_archived: false }
const ONDULEUR = { id: 202, nom: 'Onduleur réseau 10kW Triphasé', prix_vente: 10000, tva: 20, is_archived: false }

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Commercial', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

beforeEach(() => {
  vi.clearAllMocks()
  try { window.localStorage.clear() } catch { /* stockage indisponible */ }
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
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR] })
  parametresApi.getProfile.mockResolvedValue({ data: {} })
  ventesApi.getDevisById.mockResolvedValue({
    data: {
      id: 575, reference: 'DEV-202609-0575', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, client: 9,
      mode_installation: 'commercial', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000 },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '20',
          prix_unitaire: '1000.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '10000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  })
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR575 — catégorie commerciale « Non précisée » persistée null', () => {
  it('?edit= commercial sans catégorie → enregistrement avec categorie_commerciale null', async () => {
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=575']}>
          <Routes>
            <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
            <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Commercial/ })).toHaveAttribute('aria-checked', 'true'))
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    const etude = ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    expect(etude).toHaveProperty('categorie_commerciale', null)
  })
})
