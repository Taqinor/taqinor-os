// QJR571 (D-QJR5-8) — le panneau « Surcharges (registre) » DIT quels chemins
// le moteur ne lit pas : la ligne `effectif` marquée `non_lu: true` par le
// serveur porte « — sans effet sur le document ». Depuis QJR573, la liste
// blanche ne contient plus que des chemins lus : la mention ne subsiste que
// sur une surcharge RETIRÉE déjà posée en base (ici `tarif.distributeur`).
//
// Monte réellement DevisGenerator (`?edit=7` réouvre un brouillon) — aucun
// test regex sur le source (garde QJR239).
//
// Run : npx vitest run src/pages/ventes/DevisGeneratorOverridesNonLus.test.jsx
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'
import { MemoryRouter } from 'react-router-dom'

import authReducer from '../../features/auth/store/authSlice'
import ventesReducer from '../../features/ventes/store/ventesSlice'

// APIs mockées (aucun appel réseau réel au montage).
vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [] })),
    getLeads: vi.fn(() => Promise.resolve({ data: [] })),
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
    getOffresTaillesDevis: vi.fn(() => Promise.resolve({ data: { editable: false } })),
    lireOverrides: vi.fn(() => Promise.resolve({ data: {} })),
    poserOverrides: vi.fn(),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        // QJR574 — le panneau brut est réservé aux administrateurs.
        user: { id: 1 }, role: 'admin', role_nom: 'Directeur', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

// Un brouillon déjà enregistré : le panneau « Surcharges (registre) »
// n'existe QUE sur un devis avec editDevis?.id (QJR215).
const DEVIS_ROUVERT = {
  id: 7, reference: 'DEV-2026-09-0007', statut: 'brouillon', modifiable: true, raison_non_modifiable: '', revision_possible: false, is_active: true,
  mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
  lignes: [],
}

function renderGenerator() {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: [] })
  stockApi.getProduits.mockResolvedValue({ data: [] })
  ventesApi.getDevisById.mockResolvedValue({ data: DEVIS_ROUVERT })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/ventes/devis/nouveau?edit=7']}>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
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
})

const REGISTRE = {
  overrides: {
    'tarif.distributeur': { valeur: 'ONEE', origine: 'manuel' },
    scenario: { valeur: 'Sans batterie', origine: 'manuel' },
  },
  effectif: {
    'tarif.distributeur': {
      auto: null, manuel: 'ONEE', effectif: 'ONEE', source: 'manuel',
      non_derivable: true, non_lu: true,
    },
    scenario: {
      auto: 'Les deux (Sans + Avec)', manuel: 'Sans batterie',
      effectif: 'Sans batterie', source: 'manuel',
    },
  },
  lignes: {},
}

describe('QJR571 — le registre dit les chemins sans effet sur le document', () => {
  it('QJR573 — le sélecteur ne propose plus que des chemins lus, sans mention', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE })
    renderGenerator()
    await waitFor(() => expect(screen.getByTestId('overrides-panel')).toBeInTheDocument())
    const options = [...screen.getByTestId('overrides-chemin').querySelectorAll('option')]
    expect(options.map((o) => o.value)).toEqual([
      'taille.nb_panneaux', 'taille.panel_watt', 'taille.kwc',
      'scenario', 'recommended_option', 'etude.jour_reference',
    ])
    for (const o of options) expect(o.textContent).toBe(o.value)
  })

  it('la ligne `effectif` marquée non_lu le dit ; une ligne lue ne le dit pas', async () => {
    ventesApi.lireOverrides.mockResolvedValue({ data: REGISTRE })
    renderGenerator()
    await waitFor(() => expect(
      screen.getByTestId('overrides-non-lu-tarif.distributeur')).toBeInTheDocument())
    expect(screen.queryByTestId('overrides-non-lu-scenario')).toBeNull()
  })
})
