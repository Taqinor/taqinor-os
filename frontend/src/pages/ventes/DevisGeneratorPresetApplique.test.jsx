// QJR546 — appliquer un modèle REMPLACE les lignes à l'écran (édition comme
// création) : un modèle d'un autre marché pose ses lignes, sa remise, sa TVA et
// son marché ; une ligne au produit sans prix est ABSENTE et NOMMÉE ; l'étude du
// client source n'est jamais reprise. L'écran RÉEL est rendu ; ce que
// l'Enregistrer suivant envoie est lu sur les API mockées (QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorPresetApplique.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
import { estimerMois } from '../../features/ventes/solar'
import { exempleContrat } from '../../test/fixtures/contractSamples'
import { toast } from '../../ui/confirm'

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
    getPresets: vi.fn(() => Promise.resolve({ data: [] })),
    savePreset: vi.fn(),
    deletePreset: vi.fn(),
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
const PANNEAU_SANS_PRIX = {
  id: 103, nom: 'Panneau archivé 400W', prix_vente: 0, tva: 20,
  is_archived: false, prix_achat: 0,
}
const PRESET = {
  id: 9, nom: 'Modèle usine', mode_installation: 'industriel',
  taux_tva: '10.00', remise_globale: '3.00',
  etude_params_snapshot: { factures_mensuelles_reelles: [99, 99, 99] },
  lignes_snapshot: [
    { produit_id: 101, designation: 'Panneau Canadien Solar 715W', quantite: '20',
      prix_unitaire: '1000', remise: '0', taux_tva: '10' },
    { produit_id: 102, designation: 'Onduleur réseau 5kW Monophasé', quantite: '2',
      prix_unitaire: '8000', remise: '0', taux_tva: '20' },
    { produit_id: 103, designation: 'Panneau archivé 400W', quantite: '4',
      prix_unitaire: '500', remise: '0', taux_tva: '20' },
  ],
}
const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'SansStatut', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devisRouvert(variante) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', variante)
  return {
    data: {
      ...contrat, lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
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
  stockApi.getProduits.mockResolvedValue({ data: [PANNEAU, ONDULEUR, PANNEAU_SANS_PRIX] })
  ventesApi.getPresets.mockResolvedValue({ data: [PRESET] })
  crmApi.getLead.mockResolvedValue({ data: LEAD })
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR546 — un modèle appliqué remplace les lignes à l’écran', () => {
  it('modèle d’un autre marché : lignes, remise, TVA et marché posés ; produit sans prix absent et nommé', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    const avertir = vi.spyOn(toast, 'warning')
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Modèles de devis/ }))
    await userEvent.click(await screen.findByRole('button', { name: 'Appliquer' }))
    await waitFor(() => expect(avertir).toHaveBeenCalled())
    expect(avertir.mock.calls.at(-1)[0]).toMatch(/Panneau archivé 400W/)

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes, { entete }] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    const produits = lignes.map(l => Number(l.produit))
    expect(produits).toContain(PANNEAU.id)
    expect(produits).toContain(ONDULEUR.id)
    expect(produits).not.toContain(PANNEAU_SANS_PRIX.id)
    const panneaux = lignes.find(l => Number(l.produit) === PANNEAU.id)
    expect(Number(panneaux.quantite)).toBe(20)
    expect(String(entete.remise_globale)).toBe('3')
    expect(parseFloat(entete.taux_tva)).toBe(10)
    expect(entete.mode_installation).toBe('industriel')
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
  })
})
