// ERR-QJR575-SENTINELLE-CATEGORIE-NON-GARDEE — QJR575 : la catégorie
// commerciale par défaut est la sentinelle « Non précisée » (part diurne
// 80 %, la MÊME que le « Devis automatique ») et se persiste `null` — jamais
// « hôtel » par défaut (rouvrir puis enregistrer réécrivait taux / économies /
// payback). f943d00d6 avait retiré les assertions sur le source sans les
// remplacer : ce test EXÉCUTE le parcours réel (rendu React, vitest).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorCategorieCommerciale.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois, DAY_USAGE_DEFAULTS } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
    getLead: vi.fn(),
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
    getPrixApplicable: vi.fn(),
    patchDevis: vi.fn(),
    replaceLignesDevis: vi.fn(),
    createDevisAtomic: vi.fn(),
    patchEtudeParams: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

const PANNEAU = { id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10, is_archived: false }
const ONDULEUR = { id: 102, nom: 'Onduleur réseau 20kW Triphasé', prix_vente: 30000, tva: 20, is_archived: false }
const LEAD = { id: 7, nom: 'Café', prenom: 'Atlas', facture_hiver: '6000', ete_differente: false }

// Un devis COMMERCIAL dont l'étude ne porte AUCUNE categorie_commerciale
// (ex. créé par le « Devis automatique », qui ne connaît aucune catégorie).
function devisCommercial() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 43, lead: 7, client: 9, lead_nom: 'Atlas Café',
      updated_at: '2026-09-30T10:00:00Z',
      mode_installation: 'commercial', taux_tva: '20.00', remise_globale: '0',
      etude_params: { factures_mensuelles_reelles: estimerMois(6000, 6000) },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '28',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0, type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '30000.00', taux_tva: '20.00', ordre: 1, type_ligne: 'produit', optionnelle: false },
      ],
    },
  }
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

function renderEdition() {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=43']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
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
  crmApi.getLead.mockResolvedValue({ data: LEAD })
  ventesApi.getDevisById.mockResolvedValue(devisCommercial())
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('ERR-QJR575 — catégorie commerciale « Non précisée » : défaut 80 %, persistée null', () => {
  it('rouvrir un devis sans categorie_commerciale → « Non précisée », part diurne 80 % → enregistrer → categorie_commerciale: null', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    // Défaut : la sentinelle, jamais « hôtel ».
    const affichees = await screen.findAllByText('Non précisée')
    expect(affichees.some(el => el.closest('[role="combobox"]'))).toBe(true)
    expect(DAY_USAGE_DEFAULTS.Commerciale).toBe(80)
    expect(screen.getByText(/Profil de charge diurne ≈ 80 %/)).toBeTruthy()

    fireEvent.change(screen.getByPlaceholderText(/Conditions particulières/),
      { target: { value: 'Pose sous quinze jours.' } })
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer les modifications/ }))

    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled(), { timeout: 5000 })
    const [devisId, etude] = ventesApi.patchEtudeParams.mock.calls.at(-1)
    expect(devisId).toBe(43)
    // La sentinelle d'interface ne part JAMAIS au serveur : null, pas
    // 'non_precisee' ni 'hotel'.
    expect(etude).toHaveProperty('categorie_commerciale', null)
  }, 20000)
})
