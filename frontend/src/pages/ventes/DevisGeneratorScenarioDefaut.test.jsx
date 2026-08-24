// ORDRE FONDATEUR (24/08/2026) — « Tous les devis sont générés par défaut avec
// DEUX OPTIONS (sans + avec batterie), sauf si le commercial le précise sur le
// devis modifiable. »
//   • devis résidentiel VIERGE → scénario « Les deux (Sans + Avec) » ;
//   • un scénario DÉJÀ choisi (devis rouvert, lead du tunnel) l'emporte
//     toujours sur ce défaut — c'est le « sauf si » ;
//   • pompage (agricole) : jamais de scénario batterie, quoi qu'ait coché le
//     lead (le devis ne porte ni batterie ni onduleur).
// Le vocabulaire des scénarios est le contrat EXACT du moteur PDF
// (SCENARIO_* d'apps/ventes/services.py) : il n'est jamais reformulé.

import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
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
    getDevisById: vi.fn(() => Promise.resolve({ data: {} })),
    getParametresGammes: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

import crmApi from '../../api/crmApi'
import stockApi from '../../api/stockApi'
import ventesApi from '../../api/ventesApi'
import DevisGenerator from './DevisGenerator'

// Catalogue minimal : l'effet « arrivée depuis le lead » (?lead=…) n'applique
// le lead qu'une fois les produits chargés.
const PRODUITS = [
  { id: 10, nom: 'Panneau Solaire 710W', prix_vente: 1200, tva: 20, is_archived: false },
]

function makeStore() {
  return configureStore({
    reducer: { auth: authReducer, ventes: ventesReducer },
    preloadedState: {
      auth: {
        user: { id: 1 }, role: 'normal', role_nom: 'Directeur', permissions: [],
        isAuthenticated: true, loading: false,
      },
    },
  })
}

// `editId` / le lead d'arrivée sont lus dans l'URL en pleine page.
function renderGenerator({ leads = [], produits = [], route = '/ventes/devis/nouveau' } = {}) {
  crmApi.getClients.mockResolvedValue({ data: [] })
  crmApi.getLeads.mockResolvedValue({ data: leads })
  stockApi.getProduits.mockResolvedValue({ data: produits })
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[route]}>
        <DevisGenerator />
      </MemoryRouter>
    </Provider>,
  )
}

// Le Select « Scénario » est un Radix Select : son déclencheur porte l'id
// gen-scenario et affiche le LIBELLÉ de l'item sélectionné.
const scenarioAffiche = () => document.getElementById('gen-scenario')?.textContent ?? ''

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

describe('scénario par défaut d’un devis vierge', () => {
  it('résidentiel : « Les deux (Sans + Avec) » d’entrée de jeu', async () => {
    renderGenerator()
    await waitFor(() => expect(document.getElementById('gen-scenario')).toBeTruthy())
    expect(scenarioAffiche()).toContain('Les deux (Sans + Avec batterie)')
  })

  it('les deux options sont RÉELLEMENT servies : le rail montre les deux totaux', async () => {
    renderGenerator()
    await waitFor(() => expect(screen.queryByTestId('gen-rail-total')).toBeTruthy())
    expect(screen.getByText('Total sans batterie · TTC')).toBeInTheDocument()
    expect(screen.getByText('Total avec batterie · TTC')).toBeInTheDocument()
  })

  it('retour au résidentiel après un détour industriel : le défaut revient', async () => {
    renderGenerator()
    await waitFor(() => expect(document.getElementById('gen-scenario')).toBeTruthy())
    // Marché industriel : autoconsommation réseau, document à option unique.
    fireEvent.click(screen.getByRole('radio', { name: /Industriel/ }))
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
    fireEvent.click(screen.getByRole('radio', { name: /Résidentiel/ }))
    await waitFor(() => expect(scenarioAffiche()).toContain('Les deux (Sans + Avec batterie)'))
  })
})

describe('un scénario DÉJÀ choisi n’est jamais réécrit par le défaut', () => {
  it('brouillon rouvert « Avec batterie » : le choix survit à la réouverture', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: {
        id: 7, reference: 'DEV-2026-08-0007', statut: 'brouillon',
        mode_installation: 'residentiel', taux_tva: '20.00', remise_globale: '0',
        lignes: [],
        etude_params: { scenario: 'Avec batterie', recommended_choice: 'Avec batterie' },
      },
    })
    renderGenerator({ route: '/ventes/devis/nouveau?edit=7' })
    await waitFor(() => expect(scenarioAffiche()).toContain('Avec batterie seulement'))
    expect(document.getElementById('gen-reco')?.textContent).toContain('Avec batterie')
  })

  it('brouillon industriel « Les deux » : le défaut du mode ne l’écrase pas', async () => {
    ventesApi.getDevisById.mockResolvedValue({
      data: {
        id: 8, reference: 'DEV-2026-08-0008', statut: 'brouillon',
        mode_installation: 'industriel', taux_tva: '20.00', remise_globale: '0',
        lignes: [],
        etude_params: { scenario: 'Les deux (Sans + Avec)' },
      },
    })
    renderGenerator({ route: '/ventes/devis/nouveau?edit=8' })
    // On attend la PREUVE que le devis est chargé (le mode est passé à
    // industriel, qui remet par défaut « Sans batterie ») avant d'assurer que
    // le scénario enregistré, lui, a survécu.
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Industriel/ })).toHaveAttribute('aria-checked', 'true'))
    expect(scenarioAffiche()).toContain('Les deux (Sans + Avec batterie)')
  })

  it('lead du tunnel « sans batterie » : le devis part restreint, pas en double', async () => {
    renderGenerator({
      produits: PRODUITS,
      route: '/ventes/devis/nouveau?lead=42',
      leads: [{
        id: 42, nom: 'Bennani', prenom: 'Yassine',
        type_installation: 'residentiel', batterie_souhaitee: 'sans',
      }],
    })
    await waitFor(() => expect(scenarioAffiche()).toContain('Sans batterie seulement'))
  })

  it('lead sans préférence batterie : le défaut « Les deux » reste', async () => {
    renderGenerator({
      produits: PRODUITS,
      route: '/ventes/devis/nouveau?lead=43',
      leads: [{
        id: 43, nom: 'Alaoui', prenom: 'Salma',
        type_installation: 'residentiel', batterie_souhaitee: null,
      }],
    })
    // Preuve que le lead est bien appliqué avant l'assertion sur le scénario.
    await waitFor(() =>
      expect(document.getElementById('gen-lead')?.textContent).toContain('Alaoui'))
    expect(scenarioAffiche()).toContain('Les deux (Sans + Avec batterie)')
  })
})

describe('pompage (agricole) : aucun scénario batterie', () => {
  it('un lead agricole « avec batterie » ne pose PAS de scénario batterie', async () => {
    renderGenerator({
      produits: PRODUITS,
      route: '/ventes/devis/nouveau?lead=44',
      leads: [{
        id: 44, nom: 'Ouled', prenom: 'Ferme',
        type_installation: 'agricole', batterie_souhaitee: 'avec',
        pompe_cv: '5.5',
      }],
    })
    // Le mode agricole est bien pris depuis le lead…
    await waitFor(() =>
      expect(screen.getByRole('radio', { name: /Agricole/ })).toHaveAttribute('aria-checked', 'true'))
    // …et aucun scénario batterie n'a été posé au passage.
    expect(scenarioAffiche()).not.toContain('Avec batterie seulement')
  })
})
