import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { MemoryRouter } from 'react-router-dom'
import { configureStore } from '@reduxjs/toolkit'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import installationsReducer from '../installations/store/installationsSlice'
import ticketsReducer from '../sav/store/ticketsSlice'
import { applyStatutConfig } from '../installations/statuses'
import { applyTicketStatutConfig } from '../sav/ticketStatuses'

/* APAR54 — les libellés réglés dans Paramètres › Statuts doivent apparaître sur
   les écrans chantier et SAV. Les pages sont rendues pour de vrai ; seule la
   frontière API (modules *Api) est simulée. Retirer `useStatutConfig(...)` d'une
   page rend le test correspondant rouge. */

const mocks = vi.hoisted(() => ({
  getInstallations: vi.fn(),
  getTickets: vi.fn(),
  getStatutsEffective: vi.fn(),
}))

vi.mock('../../api/parametresApi', () => ({
  default: {
    getStatutsEffective: (...a) => mocks.getStatutsEffective(...a),
    getProfile: () => Promise.resolve({ data: {} }),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: (...a) => mocks.getInstallations(...a),
    getHistorique: () => Promise.resolve({ data: [] }),
    getTypesIntervention: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: { getAssignableUsers: () => Promise.resolve({ data: [] }) },
}))

vi.mock('../../api/savApi', () => ({
  default: {
    getTickets: (...a) => mocks.getTickets(...a),
    getEquipements: () => Promise.resolve({ data: [] }),
    getContrats: () => Promise.resolve({ data: [] }),
  },
}))

vi.mock('../../api/ventesApi', () => ({
  default: {
    getDevisById: () => Promise.resolve({ data: { lignes: [] } }),
    getReglementaire: () => Promise.resolve({ data: { results: [] } }),
  },
}))

import InstallationsPage from '../../pages/installations/InstallationsPage'
import TicketsPage from '../../pages/sav/TicketsPage'
import FilterBar from '../../pages/installations/FilterBar'
import KanbanView from '../../pages/installations/views/KanbanView'
import { renderInstallationDetail } from '../../test/installationDetailHarness'
import { EMPTY_FILTERS } from '../installations/statuses'

function renderPage(ui) {
  const store = configureStore({
    reducer: {
      installations: installationsReducer,
      tickets: ticketsReducer,
      auth: (state = { user: { id: 1 } }) => state,
      stock: (state = { produits: [] }) => state,
    },
  })
  return render(
    <Provider store={store}>
      <MemoryRouter>
        <ThemeProvider>{ui}</ThemeProvider>
      </MemoryRouter>
    </Provider>,
  )
}

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
  applyStatutConfig(null)
  applyTicketStatutConfig(null)
  try { localStorage.clear() } catch { /* indisponible */ }
})

describe('useStatutConfig (APAR54)', () => {
  it('chantiers : « Clôturé » renommé « Livré » dans Paramètres › Statuts s\'affiche', async () => {
    mocks.getStatutsEffective.mockResolvedValue({
      data: { results: [{ cle: 'cloture', libelle: 'Livré', ordre: 6 }] },
    })
    mocks.getInstallations.mockResolvedValue({
      data: { count: 1, results: [
        { id: 1, reference: 'CH-APAR54-1', client_nom: 'Client A', statut: 'cloture' },
      ] },
    })
    renderPage(<InstallationsPage />)
    await waitFor(() => expect(screen.getAllByText('Livré').length).toBeGreaterThan(0))
    expect(mocks.getStatutsEffective).toHaveBeenCalledWith('chantier')
  })

  it('chantiers : sans réglage, libellé par défaut', async () => {
    mocks.getStatutsEffective.mockResolvedValue({ data: { results: [] } })
    mocks.getInstallations.mockResolvedValue({
      data: { count: 1, results: [
        { id: 1, reference: 'CH-APAR54-2', client_nom: 'Client A', statut: 'cloture' },
      ] },
    })
    renderPage(<InstallationsPage />)
    await waitFor(() => expect(screen.getAllByText('CH-APAR54-2').length).toBeGreaterThan(0))
    expect(screen.queryByText('Livré')).toBeNull()
    expect(screen.getAllByText('Clôturé').length).toBeGreaterThan(0)
  })

  it('tickets SAV : « Résolu » renommé « Clos » s\'affiche (liste + filtre)', async () => {
    mocks.getStatutsEffective.mockResolvedValue({
      data: { results: [{ cle: 'resolu', libelle: 'Clos', ordre: 3 }] },
    })
    mocks.getTickets.mockResolvedValue({
      data: { count: 1, next: null, results: [
        { id: 7, reference: 'TK-APAR54-7', client_nom: 'Client B', statut: 'resolu', priorite: 'normale' },
      ] },
    })
    renderPage(<TicketsPage />)
    await waitFor(() => expect(screen.getAllByText('Clos').length).toBeGreaterThan(0))
    expect(mocks.getStatutsEffective).toHaveBeenCalledWith('sav')
  })

  it('chantiers : filtre, colonne kanban et fiche affichent le libellé réglé', async () => {
    const rename = { data: { results: [{ cle: 'cloture', libelle: 'Livré', ordre: 6 }] } }
    mocks.getStatutsEffective.mockResolvedValue(rename)
    applyStatutConfig(rename.data.results)

    // Filtre : la valeur sélectionnée porte le libellé réglé.
    const { unmount: u1 } = renderPage(
      <FilterBar filters={{ ...EMPTY_FILTERS, statut: 'cloture' }} setFilters={() => {}} items={[]} />,
    )
    expect(screen.getByLabelText('Filtrer par statut').textContent).toContain('Livré')
    u1()

    // Kanban : l'en-tête de colonne porte le libellé réglé.
    const { unmount: u2 } = renderPage(
      <KanbanView items={[]} onOpen={() => {}} onChangeStatus={() => {}} users={[]} onReassign={() => {}} />,
    )
    expect(screen.getAllByText('Livré').length).toBeGreaterThan(0)
    expect(screen.queryByText('Clôturé')).toBeNull()
    u2()

    // Fiche chantier montée seule : le hook applique le réglage à son tour.
    applyStatutConfig(null)
    renderInstallationDetail({ id: 9, reference: 'CH-APAR54-9', client_nom: 'Client C', statut: 'cloture' })
    await waitFor(() => expect(screen.getAllByText('Livré').length).toBeGreaterThan(0))
    expect(mocks.getStatutsEffective).toHaveBeenCalledWith('chantier')
  })
})
