import { describe, it, expect, vi, afterEach, beforeEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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
  updateIntervention: vi.fn(),
}))

vi.mock('../../api/installationsApi', () => ({ default: api }))
vi.mock('../../ui/confirm', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import PlanificationPage, { OutilsChantierTab, moveInterventionLocal } from './PlanificationPage'

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

/* VX251 — dispatch au glisser-déposer : réaffecter une intervention d'un
   technicien à un autre. On teste le cœur PUR de la réaffectation
   (moveInterventionLocal) : le déplacement avant, l'aller-retour « Annuler »
   (état identique), et la robustesse quand l'intervention est introuvable. */
describe('VX251 · moveInterventionLocal (réaffectation dispatch)', () => {
  const board = () => ([
    { technicien: { id: 1, nom: 'Ali' }, interventions: [{ id: 10 }, { id: 11 }] },
    { technicien: { id: 2, nom: 'Sara' }, interventions: [{ id: 20 }] },
  ])

  it("déplace l'intervention de la colonne source vers la cible", () => {
    const next = moveInterventionLocal(board(), 10, '1', '2')
    expect(next[0].interventions.map((x) => x.id)).toEqual([11])
    expect(next[1].interventions.map((x) => x.id)).toEqual([20, 10])
  })

  it("l'aller-retour (déplacer puis annuler) restaure l'état d'origine", () => {
    const start = board()
    const moved = moveInterventionLocal(start, 10, '1', '2')
    const undone = moveInterventionLocal(moved, 10, '2', '1')
    expect(undone[0].interventions.map((x) => x.id).sort()).toEqual([10, 11])
    expect(undone[1].interventions.map((x) => x.id)).toEqual([20])
  })

  it('renvoie la liste inchangée si l’intervention est introuvable', () => {
    const start = board()
    expect(moveInterventionLocal(start, 999, '1', '2')).toBe(start)
  })
})

describe('VX251 · onglet dispatch (glisser-déposer)', () => {
  it('rend des cartes intervention déplaçables + l’invite de réaffectation', async () => {
    api.getCalendrierInterventions.mockResolvedValue({
      data: [
        { technicien: { id: 1, nom: 'Ali' }, interventions: [
          { id: 10, installation_reference: 'CH-010', client_nom: 'Client A', date_prevue: '2026-07-15' },
        ] },
        { technicien: { id: 2, nom: 'Sara' }, interventions: [] },
      ],
    })
    const store = configureStore({ reducer: { auth: authReducer('responsable') } })
    render(
      <Provider store={store}>
        <PlanificationPage />
      </Provider>,
    )
    // Bascule sur l'onglet « Calendrier techniciens ».
    await userEvent.click(screen.getByText('Calendrier techniciens'))
    await waitFor(() => expect(api.getCalendrierInterventions).toHaveBeenCalled())
    await waitFor(() =>
      expect(screen.getByText(/Glissez une intervention vers un autre technicien/)).toBeInTheDocument())
    // La carte porte une poignée de déplacement accessible.
    expect(screen.getByLabelText(/Déplacer l'intervention CH-010/)).toBeInTheDocument()
  })
})
