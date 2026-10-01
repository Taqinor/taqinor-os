// QJR540 — les blocs livrés du modal DevisForm (supprimé) vivent dans
// l'Édition complète : le calepinage qui pilote le devis (CAL40), les pièces
// jointes du devis (ventes.devis), les compteurs de relations et le bandeau
// « En attente de signature client ». L'écran RÉEL est rendu ; identité/droits
// et clé `calepinage` viennent des exemples COMMITTÉS des contrats.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorEditBlocs.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'
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
vi.mock('../../api/recordsApi', () => ({
  default: {
    getAttachments: vi.fn(() => Promise.resolve({ data: [] })),
    deleteAttachment: vi.fn(),
  },
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
import recordsApi from '../../api/recordsApi'
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
  id: 77, nom: 'Khalid', prenom: 'SansStatut', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devisRouvert(variante, calepinage = 'exemple') {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', variante)
  return {
    data: {
      ...contrat, id: 12,
      ...exempleContrat('calepinage', 'calepinage_du_devis', calepinage),
      factures_liees: [{ id: 3 }], bon_commande_etat: null, chantier: null,
      layout_stale: null, layout_nb_panneaux: null,
      lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0,
          type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1,
          type_ligne: 'produit', optionnelle: false },
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

function renderEdition(id) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[`/ventes/devis/nouveau?edit=${id}`]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
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
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR540 — blocs repris de DevisForm dans l’Édition complète', () => {
  it('?edit=12 avec calepinage : bloc calepinage, pièces jointes ventes.devis 12, compteurs', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_envoye'))
    renderEdition(12)
    expect(await screen.findByTestId('cal-bloc-calepinage-devis')).toBeTruthy()
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.getByText('Pièces jointes')).toBeTruthy()
    expect(screen.getByText(/factures liées/)).toBeTruthy()
    expect(screen.getByTestId('devis-attente-signature').textContent)
      .toMatch(/En attente de signature client/)
  })

  it('brouillon sans calepinage : aucun bloc calepinage vide, pas de bandeau de signature', async () => {
    ventesApi.getDevisById.mockResolvedValue(devisRouvert('exemple_brouillon', 'exemple_vide'))
    renderEdition(12)
    await waitFor(() => expect(recordsApi.getAttachments).toHaveBeenCalledWith('ventes.devis', 12))
    expect(screen.queryByTestId('cal-bloc-calepinage-devis')).toBeNull()
    expect(screen.queryByTestId('devis-attente-signature')).toBeNull()
  })
})

