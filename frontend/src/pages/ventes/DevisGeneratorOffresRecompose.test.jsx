// QJR548 — appliquer une taille d'offre RECOMPOSE le devis côté serveur
// (pipeline RECONCILIER). L'écran doit alors relire CE devis par son chargeur
// `?edit=` : sinon il gardait ses anciennes lignes (10 panneaux) et le
// prochain « Enregistrer » annulait en silence la taille appliquée (12).
//
// L'écran RÉEL est rendu ; seul <DevisOffresTailles> est remplacé par un
// bouton qui appelle `onDevisRecompose` (son propre comportement — confirmation,
// appels réseau — est couvert par DevisOffresTailles.test.jsx).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorOffresRecompose.test.jsx
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

vi.mock('./DevisOffresTailles', () => ({
  default: ({ onDevisRecompose, modifiable }) => (
    <button type="button" data-testid="stub-appliquer-taille"
            data-modifiable={String(modifiable)}
            onClick={() => onDevisRecompose && onDevisRecompose()}>
      Appliquer la taille (stub)
    </button>
  ),
}))
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
// QJR540 — le bloc calepinage de l'Édition complète lit lui-même le devis
// (getDevisById) : neutralisé ici, ce test compte les RECHARGEMENTS de l'écran.
vi.mock('../../features/ventes/BlocCalepinageDevis', () => ({ default: () => null }))
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

const PANNEAU = {
  id: 101, nom: 'Panneau Canadien Solar 715W', prix_vente: 1200, tva: 10,
  is_archived: false, prix_achat: 800,
}
const ONDULEUR = {
  id: 102, nom: 'Onduleur réseau 5kW Monophasé', prix_vente: 9000, tva: 20,
  is_archived: false, prix_achat: 6000,
}
const LEAD = {
  id: 77, nom: 'Khalid', prenom: 'Recompose', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

function devis(nbPanneaux) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', 'exemple_brouillon')
  return {
    data: {
      ...contrat, lead: LEAD.id, client: 9,
      mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
      etude_params: {
        scenario: 'Sans batterie',
        factures_mensuelles_reelles: estimerMois(3000, 3000),
      },
      lignes: [
        { id: 1, produit: PANNEAU.id, designation: PANNEAU.nom, quantite: String(nbPanneaux),
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

describe('QJR548 — une taille appliquée recharge l\'écran depuis le devis recomposé', () => {
  it('10 panneaux, puis 12 après « appliquer » → l\'Enregistrer suivant envoie 12', async () => {
    const id = devis(10).data.id
    ventesApi.getDevisById
      .mockResolvedValueOnce(devis(10))
      .mockResolvedValueOnce(devis(12))
    renderEdition(id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    const stub = await screen.findByTestId('stub-appliquer-taille')
    // Le verdict SERVI (QJR516) descend jusqu'au bouton des tailles.
    expect(stub.getAttribute('data-modifiable')).toBe('true')

    await userEvent.click(stub)
    await waitFor(() => expect(ventesApi.getDevisById).toHaveBeenCalledTimes(2))
    expect(String(ventesApi.getDevisById.mock.calls.at(-1)[0])).toBe(String(id))

    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, lignes] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    const panneaux = lignes.filter(l => Number(l.produit) === PANNEAU.id)
    expect(panneaux).toHaveLength(1)
    expect(Number(panneaux[0].quantite)).toBe(12)
  })
})
