// QJR525 — l'Édition complète ouverte depuis la fiche lead
// (<DevisGenerator embedded leadId editId>, LeadDevisPanel) ne ré-applique
// PLUS le lead sur le devis rouvert : l'effet d'« arrivée depuis le lead »
// réécrivait les 12 factures RÉELLES stockées par une estimation à deux points
// (estimerMois(hiver, été)), sans aucun geste du vendeur, et le PATCH
// etude-params l'envoyait au serveur. La pleine page `?edit=` ne le faisait
// pas ; D-QJR5-1 fait passer la correction d'un envoyé par ce chemin.
//
// Écran RÉEL rendu, charge envoyée lue sur les API mockées.
// Run : npx vitest run src/pages/ventes/DevisGeneratorEmbeddedEdit.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'

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

import crmApi from '../../api/crmApi'
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

const LEAD = {
  id: 7, nom: 'Lead', prenom: 'Fiche', societe: '',
  type_installation: 'residentiel',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
}

// 12 factures RÉELLES distinctes (hiver ≈ 3000, comme le lead) — jamais la
// forme d'une estimation à deux points.
const FACTURES = [3000, 2950, 2700, 2400, 2200, 2100, 2300, 2350, 2250, 2500, 2800, 2980]

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
  crmApi.getLeads.mockResolvedValue({ data: [LEAD] })
  crmApi.getLead.mockResolvedValue({ data: LEAD })
  ventesApi.getDevisById.mockResolvedValue({
    data: {
      id: 42, reference: 'DEV-202609-0042', statut: 'brouillon', lead: 7, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', factures_mensuelles_reelles: FACTURES },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
      ],
    },
  })
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR525 — Édition complète embarquée : le lead n\'est pas ré-appliqué', () => {
  it('le PATCH etude-params ne porte pas estimerMois(3000, 3000) à la place des 12 factures réelles', async () => {
    render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/crm/leads/7']}>
          <DevisGenerator embedded leadId={7} editId={42} onDone={() => {}} onCancel={() => {}} />
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledWith(42))
    // Le lead ET le catalogue sont chargés (conditions de l'effet d'arrivée).
    await waitFor(() => expect(crmApi.getLeads).toHaveBeenCalled())
    await waitFor(() => expect(stockApi.getProduits).toHaveBeenCalled())
    const bouton = await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await userEvent.click(bouton)
    // Un éventuel écart à confirmer : second clic.
    if (!ventesApi.patchEtudeParams.mock.calls.length
        && screen.queryByTestId('erreur-enregistrement')) {
      await userEvent.click(bouton)
    }
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    const cles = ventesApi.patchEtudeParams.mock.calls.at(-1)[1] || {}
    expect(cles.factures_mensuelles_reelles).not.toEqual(estimerMois(3000, 3000))
    if ('factures_mensuelles_reelles' in cles) {
      expect(cles.factures_mensuelles_reelles).toEqual(FACTURES)
    }
  })
})
