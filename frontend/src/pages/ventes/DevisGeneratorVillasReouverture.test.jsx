// QJR530 — rouvrir un devis MULTI-VILLAS restaure le mode « villas » et ses
// groupes. Avant : la réouverture ne restaurait que le ×N (`nombre_proprietes`) ;
// `groupe_index` valait null hors mode 'villas' à l'enregistrement, donc
// ouvrir puis enregistrer SANS retouche dégroupait tout (même après QJR517,
// qui fait persister groupe_index / groupe_label côté serveur).
//
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorVillasReouverture.test.jsx
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
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
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
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}

const CABLE = {
  id: 103, nom: 'Câble solaire 6mm²', prix_vente: 20, tva: 20, is_archived: false,
}

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
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR, CABLE] })
  ventesApi.getDevisById.mockResolvedValue({
    data: {
      id: 530, reference: 'DEV-202609-0530', statut: 'brouillon', client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: [
        { id: 1, produit: CABLE.id, designation: CABLE.nom, quantite: '50',
          prix_unitaire: '20.00', taux_tva: '20.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false, groupe_index: 0, groupe_label: '' },
        { id: 2, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false, groupe_index: 1, groupe_label: 'Villa A' },
        { id: 3, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 2,
          type_ligne: 'produit', optionnelle: false, groupe_index: 2, groupe_label: 'Villa B' },
      ],
    },
  })
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR530 — réouverture d’un devis multi-villas', () => {
  it('restaure le mode villas : colonne Villa rendue et groupes renvoyés tels quels sans retouche', async () => {
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=530']}>
          <Routes>
            <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
            <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith('530'))
    // La colonne « Villa » de la table des lignes est rendue (mode 'villas').
    expect(await screen.findByRole('columnheader', { name: 'Villa' })).toBeInTheDocument()
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const lignes = ventesApi.replaceLignesDevis.mock.calls.at(-1)[1]
    const groupes = Object.fromEntries(lignes.map(l =>
      [l.designation, [l.groupe_index, l.groupe_label]]))
    expect(groupes).toEqual({
      [CABLE.nom]: [0, ''],
      [PANNEAU.nom]: [1, 'Villa A'],
      [ONDULEUR.nom]: [2, 'Villa B'],
    })
  })
})
