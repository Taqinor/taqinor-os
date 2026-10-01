// QJR549 (contrat QJR503, devis_verrou_edition.json) — l'Édition complète
// envoie son jeton de fraîcheur (`expected_updated_at`), le RÉ-ARME après
// chaque écriture de l'écran (ici : une taille d'offre appliquée) et, sur un
// 409 `devis_modifie`, affiche « Modifié par X » sans rien écrire d'autre.
// L'écran RÉEL est rendu ; seul <DevisOffresTailles> est remplacé par un
// bouton qui signale une écriture (`onDevisEcrit`) — son comportement réseau
// est couvert par DevisOffresTailles.test.jsx.
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorVerrouEdition.test.jsx
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
  default: ({ onDevisEcrit }) => (
    <button type="button" data-testid="stub-ecrit-taille"
            onClick={() => onDevisEcrit && onDevisEcrit('2026-09-30T09:15:00.000000+01:00')}>
      Taille écrite (stub)
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
  id: 77, nom: 'Khalid', prenom: 'SansStatut', societe: '',
  facture_hiver: '3000', ete_differente: false, facture_ete: null,
  ville: 'Mohammedia',
}

const JETON_CHARGEMENT = '2026-09-30T08:41:12.345678+01:00'
const CONFLIT = exempleContrat('ventes', 'devis_verrou_edition', 'exemple_409')

function devisRouvert(variante) {
  const contrat = exempleContrat('ventes', 'devis_modifiabilite', variante)
  return {
    data: {
      ...contrat, lead: LEAD.id, client: 9, date_envoi: '2026-09-28T10:00:00Z',
      updated_at: JETON_CHARGEMENT,
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

describe('QJR549 — verrou optimiste de l’Édition complète', () => {
  it('409 devis_modifie → bannière « Modifié par … », rien d’autre écrit', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis.mockRejectedValue({ response: { status: 409, data: CONFLIT } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    const banniere = await screen.findByTestId('devis-verrou-banner')
    expect(banniere.textContent).toMatch(new RegExp(`Modifié par ${CONFLIT.updated_by_nom}`))
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra.expected_updated_at).toBe(JETON_CHARGEMENT)
    expect(ventesApi.patchEtudeParams).not.toHaveBeenCalled()
    expect(ventesApi.patchDevis).not.toHaveBeenCalled()
    expect(screen.queryByText('APRES-ENREGISTREMENT')).toBeNull()
  })

  it('« Enregistrer quand même » renvoie UNE fois sans jeton', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis
      .mockRejectedValueOnce({ response: { status: 409, data: CONFLIT } })
      .mockResolvedValueOnce({ data: { updated_at: '2026-09-30T10:00:00+01:00' } })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await screen.findByTestId('devis-verrou-banner')
    await userEvent.click(screen.getByRole('button', { name: /Enregistrer quand même/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalledTimes(2))
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra).not.toHaveProperty('expected_updated_at')
  })

  it('après une écriture de l’écran (taille appliquée), la sauvegarde envoie le NOUVEAU jeton', async () => {
    const rouvert = devisRouvert('exemple_brouillon')
    ventesApi.getDevisById.mockResolvedValue(rouvert)
    ventesApi.replaceLignesDevis.mockResolvedValue({ data: {} })
    renderEdition(rouvert.data.id)
    await waitFor(() => expect(crmApi.getLead).toHaveBeenCalledWith(77))
    await userEvent.click(await screen.findByTestId('stub-ecrit-taille'))
    await userEvent.click(await screen.findByRole('button', { name: /Enregistrer les modifications/ }))
    await waitFor(() => expect(ventesApi.replaceLignesDevis).toHaveBeenCalled())
    const [, , extra] = ventesApi.replaceLignesDevis.mock.calls.at(-1)
    expect(extra.expected_updated_at).toBe('2026-09-30T09:15:00.000000+01:00')
    expect(extra.expected_updated_at).not.toBe(JETON_CHARGEMENT)
  })
})
