// NTMOB25 — accueil mobile « Technicien responsable » : vue d'équipe du jour
// + réaffectation, redirection desktop.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const { coreApiMock, installationsApiMock, isMobileMock } = vi.hoisted(() => ({
  coreApiMock: { utilisateurs: { list: vi.fn() } },
  installationsApiMock: {
    getInterventions: vi.fn(),
    getConflitsAffectation: vi.fn(),
    updateIntervention: vi.fn(),
  },
  isMobileMock: vi.fn(() => true),
}))
vi.mock('../../../api/coreApi', () => ({ default: coreApiMock }))
vi.mock('../../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 7 } } }),
}))
vi.mock('../../../ui/ResponsiveDialog', async () => {
  const actual = await vi.importActual('../../../ui/ResponsiveDialog')
  return { ...actual, useIsMobile: () => isMobileMock() }
})

import EquipeTerrainHome from './EquipeTerrainHome'

beforeEach(() => {
  vi.clearAllMocks()
  isMobileMock.mockReturnValue(true)
  coreApiMock.utilisateurs.list.mockResolvedValue({
    data: [
      { id: 11, username: 'karim', supervisor: 7 },
      { id: 12, username: 'said', supervisor: 7 },
      // Hors équipe : rattaché à un autre responsable.
      { id: 13, username: 'autre', supervisor: 99 },
    ],
  })
  installationsApiMock.getInterventions.mockResolvedValue({
    data: {
      results: [
        { id: 1, technicien: 11, client_nom: 'Client A', site_ville: 'Casablanca' },
        { id: 2, technicien: 13, client_nom: 'Client hors équipe' },
      ],
    },
  })
  installationsApiMock.getConflitsAffectation.mockResolvedValue({ data: { conflits: [] } })
  installationsApiMock.updateIntervention.mockResolvedValue({ data: {} })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/mobile/equipe-terrain']}>
      <Routes>
        <Route path="/mobile/equipe-terrain" element={<EquipeTerrainHome />} />
        <Route path="/dashboard" element={<div>Dashboard desktop</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('EquipeTerrainHome (NTMOB25)', () => {
  it('redirige vers le dashboard en desktop', () => {
    isMobileMock.mockReturnValue(false)
    renderPage()
    expect(screen.getByText('Dashboard desktop')).toBeTruthy()
  })

  it("n'affiche que les interventions des subordonnés directs", async () => {
    renderPage()
    expect(await screen.findByText('Client A')).toBeTruthy()
    expect(screen.queryByText('Client hors équipe')).toBeNull()
    // Le nom du technicien de l'équipe est affiché sous l'intervention.
    expect(screen.getByText(/karim — Casablanca/)).toBeTruthy()
  })

  it('propose de réaffecter à un collègue de l\'équipe', async () => {
    renderPage()
    await screen.findByText('Client A')
    expect(screen.getByLabelText("Réaffecter l'intervention 1")).toBeTruthy()
  })

  it('affiche les conflits d\'affectation quand il y en a', async () => {
    installationsApiMock.getConflitsAffectation.mockResolvedValue({
      data: { conflits: [{ id: 5, libelle: 'karim : 2 interventions à 9h' }] },
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByText('karim : 2 interventions à 9h')).toBeTruthy()
    })
  })
})
