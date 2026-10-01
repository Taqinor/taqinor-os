// QJR572 — Scénario, Option recommandée et nombre de panneaux de l'Édition
// complète suivent le REGISTRE de surcharges (il gagne au PDF) : une surcharge
// posée s'affiche à la réouverture, et la changer à l'écran met le registre
// à jour à l'enregistrement. Registre vide → aucun appel au registre.
//
// L'écran RÉEL est rendu (`?edit=<id>`) ; ce que l'enregistrement envoie est
// lu sur les API mockées (garde QJR239 : aucun regex sur le source).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorRegistreEcran.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'
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
    getDevisById: vi.fn(),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
    getPrefillSite: vi.fn(() => Promise.resolve({ data: {} })),
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(),
    poserOverrides: vi.fn(),
    regenererOverride: vi.fn(),
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

const LES_DEUX = 'Les deux (Sans + Avec)'
const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}

function devisRouvert() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, client: 9, lead: null,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: LES_DEUX },
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

const registre = (effectif) => ({ overrides: {}, effectif, lignes: {} })
const REGISTRE_SANS = registre({
  scenario: { auto: LES_DEUX, manuel: 'Sans batterie', effectif: 'Sans batterie', source: 'manuel' },
})
const REGISTRE_VIDE = registre({
  scenario: { auto: LES_DEUX, manuel: null, effectif: LES_DEUX, source: 'auto' },
})

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

const scenarioAffiche = () => document.getElementById('gen-scenario')?.textContent ?? ''

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
  ventesApi.getDevisById.mockResolvedValue(devisRouvert())
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
  ventesApi.poserOverrides.mockImplementation((_id, patch) => Promise.resolve({
    data: registre({ scenario: { auto: LES_DEUX, manuel: patch.scenario?.valeur,
      effectif: patch.scenario?.valeur, source: 'manuel' } }),
  }))
})

async function enregistrer() {
  await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
  await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(1))
}

describe('QJR572 — l’écran suit le registre de surcharges', () => {
  it('un scénario imposé par le registre s’affiche à la réouverture, avec le retour à l’automatique', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_SANS })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
    expect(screen.getByTestId('registre-impose-scenario')).toHaveTextContent(/revenir à l.automatique/)
  })

  it('changer le scénario imposé puis enregistrer pose la nouvelle valeur au registre', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_SANS })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
    await userEvent.click(document.getElementById('gen-scenario'))
    await userEvent.click(await screen.findByRole('option', { name: /Les deux/ }))
    await waitFor(() => expect(scenarioAffiche()).toContain('Les deux'))
    await enregistrer()
    await waitFor(() => expect(ventesApi.poserOverrides).toHaveBeenCalledTimes(1))
    const [id, patch] = ventesApi.poserOverrides.mock.calls[0]
    expect(id).toBe(devisRouvert().data.id)
    expect(patch).toEqual({ scenario: { valeur: LES_DEUX } })
    expect(ventesApi.regenererOverride).not.toHaveBeenCalled()
  })

  it('registre sans surcharge : l’enregistrement n’écrit rien au registre', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE_VIDE })
    renderEdition(devisRouvert().data.id)
    await waitFor(() => expect(ventesApi.lireOverrides).toHaveBeenCalled())
    expect(screen.queryByTestId('registre-impose-scenario')).toBeNull()
    await enregistrer()
    expect(ventesApi.poserOverrides).not.toHaveBeenCalled()
    expect(ventesApi.regenererOverride).not.toHaveBeenCalled()
  })
})
