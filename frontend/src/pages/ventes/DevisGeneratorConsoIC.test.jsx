// QJR582 — en industriel / commercial, la facture réelle « recommandée »
// alimente l'étude ET la validation quand le champ « Consommation mensuelle —
// pour l'étude » est vide. Avant, validate() bloquait un devis industriel dont
// seule la facture réelle était remplie.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorConsoIC.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { kwhFromBill } from '../../features/ventes/solar'
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

const PANNEAU = { id: 101, nom: 'Panneau Canadien Solar 710W', prix_vente: 1100, tva: 10, is_archived: false }
const ONDULEUR = { id: 102, nom: 'Onduleur réseau 50kW Triphasé', prix_vente: 60000, tva: 20, is_archived: false }

function devisIndustriel() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 55, lead: 8, client: 9, lead_nom: 'Usine Atlas',
      mode_installation: 'industriel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie' },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '100',
          prix_unitaire: '1000.00', taux_tva: '10.00', ordre: 0, type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '50000.00', taux_tva: '20.00', ordre: 1, type_ligne: 'produit', optionnelle: false },
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
  // Lead SANS facture : aucune autre source de consommation.
  crmApi.getLead.mockResolvedValue({ data: { id: 8, nom: 'Usine', prenom: 'Atlas' } })
  ventesApi.getDevisById.mockResolvedValue(devisIndustriel())
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR582 — industriel : la facture réelle alimente l\'étude et la validation', () => {
  it('seule la facture réelle est remplie → aucune erreur conso, conso_annuelle de l\'étude dérivée d\'elle', async () => {
    const { container } = render(
      <Provider store={makeStore()}>
        <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=55']}>
          <Routes>
            <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
            <Route path="*" element={<div>APRES</div>} />
          </Routes>
        </MemoryRouter>
      </Provider>,
    )
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(8))
    await waitFor(() => expect(container.querySelector('#gen-realbill')).not.toBeNull())
    fireEvent.change(container.querySelector('#gen-realbill'), { target: { value: '12000' } })

    fireEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.patchEtudeParams).toHaveBeenCalled())
    expect(screen.queryByText(/Mode industriel : renseignez la consommation/)).toBeNull()

    // Facture réelle 12 000 MAD/mois au barème ONEE (mode MAD par défaut) →
    // conso mensuelle réelle → étude (kWh/mois × 12).
    const consoAnnuelleReelle = Math.round(kwhFromBill(12000, 'onee').kwhMensuel * 12)
    const attendu = Math.round(Math.round(consoAnnuelleReelle / 12) * 12)
    const [, bloc] = ventesApi.patchEtudeParams.mock.calls.at(-1)
    expect(bloc.conso_annuelle).toBe(attendu)
    expect(bloc.taux_autoconso).toEqual(expect.any(Number))
  })
})
