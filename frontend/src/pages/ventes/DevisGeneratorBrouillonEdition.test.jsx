// QJR581 — ouvrir un devis sans rien changer ne crée plus de « brouillon non
// enregistré » ; un brouillon local périmé (devis modifié depuis) n'est jamais
// proposé ; la garde de sortie se désarme après un enregistrement réussi.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorBrouillonEdition.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
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

const CLE = 'taqinor:draft:devis:edit:42'
const UPDATED_AT = '2026-09-30T10:00:00Z'
const PANNEAU = { id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10, is_archived: false }
const ONDULEUR = { id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20, is_archived: false }
const LEAD = { id: 7, nom: 'Karim', prenom: 'Brouillon', facture_hiver: '2000', ete_differente: false }

function devis42() {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, id: 42, lead: 7, client: 9, lead_nom: 'Karim Brouillon',
      updated_at: UPDATED_AT,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', factures_mensuelles_reelles: estimerMois(2000, 2000) },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: '8',
          prix_unitaire: '1200.00', taux_tva: '10.00', ordre: 0, type_ligne: 'produit', optionnelle: false },
        { id: 2, produit: ONDULEUR.id, designation: ONDULEUR.nom, quantite: '1',
          prix_unitaire: '9000.00', taux_tva: '20.00', ordre: 1, type_ligne: 'produit', optionnelle: false },
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
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=42']}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

const quitterBloque = () => {
  const ev = new Event('beforeunload', { cancelable: true })
  window.dispatchEvent(ev)
  return ev.defaultPrevented
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
  ventesApi.getDevisById.mockResolvedValue(devis42())
  ventesApi.patchDevis.mockResolvedValue({ data: {} })
  ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
  ventesApi.patchEtudeParams.mockResolvedValue({ data: {} })
})

describe('QJR581 — brouillon local en Édition complète', () => {
  it('rouvrir le devis 42 sans rien changer : aucun brouillon écrit, aucune garde de sortie', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 2200))
    expect(window.localStorage.getItem(CLE)).toBeNull()
    expect(quitterBloque()).toBe(false)
  }, 15000)

  it('brouillon local à updated_at ancien : aucun bandeau « Reprendre », brouillon purgé', async () => {
    window.localStorage.setItem(CLE, JSON.stringify({
      savedAt: '2026-09-29T08:00:00Z', version: '2026-09-29T07:00:00Z', data: { note: 'vieux' },
    }))
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(window.localStorage.getItem(CLE)).toBeNull())
    expect(screen.queryByTestId('draft-restore-banner')).toBeNull()
  })

  it('brouillon local à updated_at courant : « Reprendre » proposé', async () => {
    window.localStorage.setItem(CLE, JSON.stringify({
      savedAt: '2026-09-30T11:00:00Z', version: UPDATED_AT, data: { note: 'récent' },
    }))
    renderEdition()
    expect(await screen.findByTestId('draft-restore-banner')).toBeTruthy()
  })

  it('après un enregistrement réussi : la garde de sortie est désarmée', async () => {
    renderEdition()
    await screen.findByRole('button', { name: /Enregistrer les modifications/ })
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(7))
    await new Promise(r => setTimeout(r, 1700))
    fireEvent.change(screen.getByPlaceholderText(/Conditions de paiement/), { target: { value: 'Acompte 30 %' } })
    await waitFor(() => expect(quitterBloque()).toBe(true))
    fireEvent.click(screen.getByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    await waitFor(() => expect(quitterBloque()).toBe(false))
  }, 15000)
})
