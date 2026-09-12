import { describe, it, expect, vi, beforeAll, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* ============================================================================
   CHT21(c) — Deep-link cassé du parcours commercial : « Voir le client »
   naviguait vers la liste nue `/crm` (générique) ; même patron que « Voir le
   lead » voisin (`?id=` déjà lu par `ClientList.jsx:73`, VX79).
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

vi.mock('../../api/gestionProjetApi', () => ({
  default: {
    getChantiers: () => Promise.resolve({ data: { results: [] } }),
    creerProjetDepuisDevis: () => Promise.resolve({ data: { id: 1, code: 'PRJ-0001' } }),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getEquipements: () => Promise.resolve({ data: [] }),
    getTickets: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getAssignableUsers: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
})

import InstallationDetail from './InstallationDetail'

function makeStore() {
  return configureStore({
    reducer: {
      stock: (state = { produits: [{ id: 1, nom: 'Panneau' }] }) => state,
    },
  })
}

function renderDetail(installation) {
  return render(
    <Provider store={makeStore()}>
      <MemoryRouter initialEntries={['/chantiers']}>
        <ThemeProvider>
          <InstallationDetail installation={installation} onClose={() => {}} onSaved={() => {}} />
        </ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('InstallationDetail — « Voir le client » cible la fiche réelle (CHT21c)', () => {
  it('navigue vers /crm?id=<client> (jamais la liste nue)', async () => {
    const user = userEvent.setup()
    renderDetail({
      id: 701, reference: 'CH-CHT21-701', statut: 'signe', annule: false,
      client: 33, client_nom: 'Client CHT21',
    })

    const bouton = await screen.findByRole('button', { name: 'Voir le client' })
    await user.click(bouton)
    expect(navigateMock).toHaveBeenCalledWith('/crm?id=33')
  })

  it("n'affiche rien quand le chantier n'a aucun client", async () => {
    renderDetail({
      id: 702, reference: 'CH-CHT21-702', statut: 'signe', annule: false,
      client: null,
    })
    expect(screen.queryByRole('button', { name: 'Voir le client' })).toBeNull()
  })
})
