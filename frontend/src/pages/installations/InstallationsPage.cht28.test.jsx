import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import installationsReducer from '../../features/installations/store/installationsSlice'

/* ============================================================================
   CHT28 — InstallationsPage.jsx n'avait AUCUN test unitaire : (1) rendu liste
   (les chantiers chargés apparaissent, le compte du titre reflète le total
   filtré) et (2) deep-link `?id=` ouvre la fiche du chantier ciblé en Sheet
   (VX79, déjà exercé par notification/lien copié — jamais testé côté écran).
   ----------------------------------------------------------------------------
   Piège RTL connu (mémoire, "4 pièges RTL") : DataTable rend en DOUBLE sous
   jsdom (le responsive mobile/desktop ne s'applique pas sans vrai viewport,
   les deux mises en page restent dans le DOM) — `getAllByText`/
   `toBeGreaterThan(0)` partout où une cellule de ligne est lue, JAMAIS
   `getByText` qui échouerait en mode strict. Le second piège (heading
   ambigu : le SheetTitle de la fiche ouverte contient AUSSI « Chantier ») est
   évité en scopant chaque assertion (dialog / texte précis), jamais un
   `getByRole('heading', /chantier/i)` générique.
   ========================================================================== */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

const mocks = vi.hoisted(() => ({
  getInstallations: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: (...args) => mocks.getInstallations(...args),
    // Appelés au montage de InstallationDetail (deep-link) — voir
    // InstallationDetail.cht18/20/21/22.test.jsx pour le même patron.
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getChantiers: () => Promise.resolve({ data: { results: [] } }),
    creerProjetDepuisDevis: () => Promise.resolve({ data: { id: 1, code: 'PRJ-0001' } }),
  },
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

import InstallationsPage from './InstallationsPage'

function makeStore() {
  return configureStore({
    reducer: {
      installations: installationsReducer,
      auth: (state = { user: { id: 1 } }) => state,
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
    },
  })
}

function renderPage(route = '/chantiers') {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={[route]}>
        <ThemeProvider>
          <InstallationsPage />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  try { localStorage.clear() } catch { /* indisponible */ }
})

describe('InstallationsPage (CHT28)', () => {
  it('rendu liste : les chantiers chargés apparaissent, le titre reflète le total', async () => {
    mocks.getInstallations.mockResolvedValue({
      data: {
        count: 2,
        results: [
          { id: 11, reference: 'CH-CHT28-011', client_nom: 'Client A', statut: 'signe' },
          { id: 12, reference: 'CH-CHT28-012', client_nom: 'Client B', statut: 'planifie' },
        ],
      },
    })
    renderPage()

    await waitFor(() => expect(
      screen.getAllByText('CH-CHT28-011').length,
    ).toBeGreaterThan(0))
    expect(screen.getAllByText('CH-CHT28-012').length).toBeGreaterThan(0)

    // Une seule fiche h2 à ce stade (aucun Sheet ouvert) : sans ambiguïté.
    const titre = screen.getByRole('heading', { level: 2 })
    expect(titre).toHaveTextContent('Chantiers')
    expect(titre).toHaveTextContent('2')
  })

  it("deep-link ?id= ouvre la fiche du chantier ciblé en Sheet (VX79)", async () => {
    mocks.getInstallations.mockResolvedValue({
      data: {
        count: 1,
        results: [
          { id: 21, reference: 'CH-CHT28-021', client_nom: 'Client Deep', statut: 'signe' },
        ],
      },
    })
    renderPage('/chantiers?id=21')

    await waitFor(() => expect(screen.getByRole('dialog')).toBeVisible())
    expect(screen.getAllByText(/CH-CHT28-021/).length).toBeGreaterThan(0)
  })
})
