import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* WR10 — PlanificationPage : câble les surfaces de scheduling/logistique
   (Gantt chantiers FG74, calendrier techniciens FG68, ma tournée FG73, plan de
   charge / conflits / nivellement FG299-301, camionnettes FG303, outils
   chantier N43/FG79/FG71). On vérifie : (1) le Gantt appelle bien
   getGanttChantiers et rend une barre par chantier daté ; (2) les onglets
   existent (hooks e2e data-testid) ; (3) la synthèse coût/marge (admin-only)
   n'apparaît PAS pour un rôle non-admin. Toute la logique réseau est mockée. */

const api = vi.hoisted(() => ({
  getGanttChantiers: vi.fn(),
  getCalendrierInterventions: vi.fn(),
  getMaTournee: vi.fn(),
  getPlanDeCharge: vi.fn(),
  getConflitsAffectation: vi.fn(),
  getNivellementCharge: vi.fn(),
  getPlanningCamionnettes: vi.fn(),
  getInstallations: vi.fn(),
  getRegimeSuggestion: vi.fn(),
  creerInterventionsStandard: vi.fn(),
  getChantierCout: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))
vi.mock('../../ui/confirm', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import PlanificationPage, { OutilsChantierTab } from './PlanificationPage'

function authReducer(role) {
  return (state = { role }) => state
}

function renderPage(role = 'responsable') {
  const store = configureStore({ reducer: { auth: authReducer(role) } })
  return render(
    <Provider store={store}>
      <PlanificationPage />
    </Provider>,
  )
}

function renderOutils(role = 'responsable') {
  const store = configureStore({ reducer: { auth: authReducer(role) } })
  return render(
    <Provider store={store}>
      <OutilsChantierTab />
    </Provider>,
  )
}

beforeEach(() => {
  api.getGanttChantiers.mockResolvedValue({
    data: [
      {
        id: 1, reference: 'CH-001', client_nom: 'Client A', statut: 'planifie',
        jalons: { signature: '2026-01-01', cloture: '2026-02-01' },
      },
    ],
  })
  api.getCalendrierInterventions.mockResolvedValue({ data: [] })
  api.getMaTournee.mockResolvedValue({ data: { stops: [] } })
  api.getPlanDeCharge.mockResolvedValue({ data: { techniciens: [], jours_ouvres: 5, capacite_heures: 40 } })
  api.getConflitsAffectation.mockResolvedValue({ data: { conflits: [] } })
  api.getNivellementCharge.mockResolvedValue({ data: { propositions: [] } })
  api.getPlanningCamionnettes.mockResolvedValue({ data: { camionnettes: [] } })
  api.getInstallations.mockResolvedValue({ data: [] })
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('PlanificationPage (WR10)', () => {
  it('charge et affiche le Gantt multi-chantier', async () => {
    renderPage()
    await waitFor(() => expect(api.getGanttChantiers).toHaveBeenCalled())
    await waitFor(() =>
      expect(document.querySelector('[data-testid="gantt-chantiers"]')).toBeInTheDocument())
    expect(screen.getByText('CH-001')).toBeInTheDocument()
  })

  it('rend tous les onglets de planification', () => {
    renderPage()
    expect(screen.getByText('Gantt chantiers')).toBeInTheDocument()
    expect(screen.getByText('Calendrier techniciens')).toBeInTheDocument()
    expect(screen.getByText('Ma tournée')).toBeInTheDocument()
    expect(screen.getByText('Plan de charge')).toBeInTheDocument()
    expect(screen.getByText('Camionnettes')).toBeInTheDocument()
    expect(screen.getByText('Outils chantier')).toBeInTheDocument()
  })

  it('outils chantier : ne montre PAS la synthèse coût/marge pour un non-admin', async () => {
    renderOutils('responsable')
    await waitFor(() => expect(api.getInstallations).toHaveBeenCalled())
    // Les outils N43 (régime) + FG79 (interventions standard) restent visibles…
    expect(screen.getByText(/Suggestion de régime/)).toBeInTheDocument()
    // …mais la synthèse coût/marge (FG71, INTERNE) est masquée.
    expect(screen.queryByText(/Synthèse coût \/ marge/)).toBeNull()
  })

  it('outils chantier : montre la synthèse coût/marge pour un admin', async () => {
    renderOutils('admin')
    await waitFor(() => expect(api.getInstallations).toHaveBeenCalled())
    expect(screen.getByText(/Synthèse coût \/ marge/)).toBeInTheDocument()
  })
})
