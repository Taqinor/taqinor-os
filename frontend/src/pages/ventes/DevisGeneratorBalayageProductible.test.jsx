// ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — le balayage `optimalKwcByPayback`
// du générateur (marchés sans moteur serveur) chiffre la production au
// productible de la VILLE DU LEAD, comme l'aperçu (`roi`) et le PDF — jamais
// au repli historique GHI × 0,8 de `computeROI`.
//
// L'écran RÉEL est rendu via `?lead=` (applyLead → computeAutoSizing) ; seul
// `optimalKwcByPayback` est espionné — aucune lecture de source (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorBalayageProductible.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, waitFor } from '@testing-library/react'
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
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))
vi.mock('../../api/parametresApi', () => ({
  default: { getProfile: vi.fn(() => Promise.resolve({ data: {} })) },
}))
vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))
vi.mock('../../features/ventes/solar', async (importOriginal) => {
  const original = await importOriginal()
  return {
    ...original,
    // Aucun palier retenu : seuls les ARGUMENTS du balayage sont lus.
    optimalKwcByPayback: vi.fn(() => ({ nbPanneaux: 0 })),
  }
})

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import { optimalKwcByPayback, productibleForCity } from '../../features/ventes/solar'
import DevisGenerator from './DevisGenerator'

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
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
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU] })
})

describe('ERR-QAH-DIFF-ROI-PRODUCTIBLE-DEFAUT — balayage du générateur', () => {
  it('lead industriel de Agadir : le balayage reçoit le productible de SA ville', async () => {
    crmApi.getLeads.mockResolvedValue({ data: [{
      id: 42, nom: 'Usine', prenom: 'Sud', type_installation: 'industriel',
      facture_hiver: '4000', ete_differente: false, ville: 'Agadir',
    }] })
    // Garde du témoin : la ville change bien le productible.
    expect(productibleForCity('Agadir')).not.toBe(productibleForCity(''))
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?lead=42']}>
          <DevisGenerator />
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(optimalKwcByPayback).toHaveBeenCalled())
    for (const [args] of optimalKwcByPayback.mock.calls) {
      expect(args.productible).toBe(productibleForCity('Agadir'))
    }
  })

  it('QJR586 — douar hors gazetier rattaché à Agadir : le balayage lit la ville de CALCUL servie', async () => {
    crmApi.getLeads.mockResolvedValue({ data: [{
      id: 43, nom: 'Ferme', prenom: 'Douar', type_installation: 'industriel',
      facture_hiver: '4000', ete_differente: false,
      ville: 'Sidi Hashass', ville_reference: 'Agadir', ville_effective: 'Agadir',
    }] })
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?lead=43']}>
          <DevisGenerator />
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(optimalKwcByPayback).toHaveBeenCalled())
    for (const [args] of optimalKwcByPayback.mock.calls) {
      expect(args.productible).toBe(productibleForCity('Agadir'))
    }
  })
})
