// QJR641 — le sélecteur « Type d'installation » disparaît : le Marché est la
// seule source, et le défaut de la part diurne en dérive. Le curseur est
// masqué en commercial et en agricole.
// Écran RÉEL rendu (jamais une lecture du source).
// Run : npx vitest run src/pages/ventes/DevisGeneratorTypeInstallation.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

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
  parametresApi.getProfile.mockResolvedValue({ data: {} })
  ventesApi.getDevisById.mockResolvedValue({
    data: {
      id: 528, reference: 'DEV-202609-0528', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true, client: 9,
      mode_installation: 'industriel', taux_tva: '20.00', remise_globale: '0',
      etude_params: { scenario: 'Sans batterie', conso_annuelle: 60000, part_diurne_pct: 65 },
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

function rendre(url) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[url]}>
        <Routes>
          <Route path="/ventes/devis/nouveau" element={<DevisGenerator />} />
          <Route path="*" element={<div>APRES-ENREGISTREMENT</div>} />
        </Routes>
      </MemoryRouter>
    </Provider>,
  )
}

const curseur = () => screen.queryByTestId('curseur-part-diurne')

describe('QJR641 — plus de « Type d’installation » : le Marché pilote la part diurne', () => {
  it('nouveau devis : aucun sélecteur de type, pas de curseur, défaut résidentiel (60 %) affiché', async () => {
    rendre('/ventes/devis/nouveau')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Résidentiel/ })).toHaveAttribute('aria-checked', 'true'))
    expect(document.getElementById('gen-insttype')).toBeNull()
    expect(screen.queryByText(/Type d'Installation/)).toBeNull()
    // AGNR44 — plus de curseur : la part diurne par défaut est DITE (60 %).
    expect(curseur()).toBeNull()
    expect(screen.getByTestId('part-diurne-defaut').textContent).toMatch(/60 %/)
  })

  it('CIQ126 — Industriel, Commercial et Agricole : curseur masqué (profil déclaré au moteur C&I)', async () => {
    const user = userEvent.setup()
    rendre('/ventes/devis/nouveau')
    await user.click(await screen.findByRole('radio', { name: /Industriel/ }))
    await waitFor(() => expect(curseur()).toBeNull())
    await user.click(screen.getByRole('radio', { name: /Commercial/ }))
    await waitFor(() => expect(curseur()).toBeNull())
    await user.click(screen.getByRole('radio', { name: /Agricole/ }))
    await waitFor(() => expect(curseur()).toBeNull())
  })

  it('CIQ126 — réouverture industrielle : part_diurne_pct n’est plus relue, aucun curseur', async () => {
    rendre('/ventes/devis/nouveau?edit=528')
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    await screen.findByTestId('ci-profil')
    expect(curseur()).toBeNull()
  })
})
