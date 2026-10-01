// QJR527 — l'Édition complète (`?edit=`) charge AUSSI les réglages société
// (tarif kWh, rendement, TVA, productible, remise max) et relit le prix cible
// DU DEVIS. Avant : l'effet des réglages sortait dès qu'editId était posé —
// l'étude industrielle était re-persistée au tarif par défaut du code (et
// imprimée), et chaque enregistrement en édition EFFAÇAIT prix_cible_kwc.
//
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorReglagesEdition.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import {
  computeEtudeIndustrielle, DAY_USAGE_DEFAULTS, EFFICIENCY,
} from '../../features/ventes/solar'

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
  parametresApi.getProfile.mockResolvedValue({
    data: { onee_tarif_kwh: 1.5, prix_cible_kwc_defaut: 9000 },
  })
  ventesApi.getDevisById.mockResolvedValue({
    data: {
      id: 510, reference: 'DEV-202609-0510', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, client: 9,
      mode_installation: 'industriel', taux_tva: '20.00', remise_globale: '0',
      prix_cible_kwc: '8500.00',
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

describe('QJR527 — Édition complète : réglages société chargés, prix cible du devis relu', () => {
  it('renvoie prix_cible_kwc du devis et re-persiste l\'étude au tarif SOCIÉTÉ', async () => {
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=510']}>
          <Routes>
            <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
            <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalled())
    await waitFor(() => expect(parametresApi.getProfile).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())

    // La cible DU DEVIS gagne (jamais effacée, jamais le défaut société 9000).
    const payload = ventesApi.replaceLignesDevis.mock.calls.at(-1)[2].entete
    expect(payload.prix_cible_kwc).toBe('8500')

    // L'étude est re-persistée au tarif kWh de la société (1,5), pas au 1,75 du code.
    const attendu = computeEtudeIndustrielle({
      kwp: 20 * 550 / 1000, consoMensuelleKwh: 5000,
      dayUsagePct: DAY_USAGE_DEFAULTS.Industrielle, totalTtc: 20 * 1100 + 12000,
      kwhPrice: 1.5, efficiency: EFFICIENCY,
    })
    const etude = ventesApi.patchEtudeParams.mock.calls.at(-1)[1]
    expect(etude.payback).toBe(attendu.payback)
  })
})
