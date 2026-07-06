import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import TachesPage from './TachesPage'

/* XPRJ10-12 — Écran transverse des tâches : filtres (assigné/priorité/statut)
   + bascule liste/kanban, et mode « Mes tâches » (mes-taches, transverse aux
   projets pour l'utilisateur courant, sans filtres). */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getTaches: vi.fn(() => Promise.resolve({
      data: [{ id: 1, libelle: 'Pose panneaux', projet_code: 'P-1', priorite: 'haute', statut: 'a_faire', assigne_nom: 'Amine' }],
    })),
    getRessources: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Amine' }] })),
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getMesTaches: vi.fn(() => Promise.resolve({
      data: [{ id: 2, libelle: 'Ma tâche urgente', projet_code: 'P-2', priorite: 'urgente', statut: 'en_cours' }],
    })),
    getChronoActif: vi.fn(() => Promise.resolve({ status: 204, data: null })),
    updateTache: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('TachesPage', () => {
  it('charge et affiche les tâches filtrées par projet/assigné/priorité/statut', async () => {
    withProviders(<TachesPage />)
    await waitFor(() => expect(gestionProjetApi.getTaches).toHaveBeenCalled())
    expect((await screen.findAllByText('Pose panneaux')).length).toBeGreaterThan(0)
  })

  it('changer le filtre priorité relance le chargement avec le bon paramètre', async () => {
    const user = userEvent.setup()
    withProviders(<TachesPage />)
    await waitFor(() => expect(gestionProjetApi.getTaches).toHaveBeenCalled())
    await user.selectOptions(screen.getByLabelText('Filtrer par priorité'), 'haute')
    await waitFor(() => expect(gestionProjetApi.getTaches).toHaveBeenCalledWith(
      expect.objectContaining({ priorite: 'haute' }),
    ))
  })

  it('mode « Mes tâches » appelle mes-taches et masque les filtres', async () => {
    withProviders(<TachesPage mesTaches />)
    await waitFor(() => expect(gestionProjetApi.getMesTaches).toHaveBeenCalled())
    expect((await screen.findAllByText('Ma tâche urgente')).length).toBeGreaterThan(0)
    expect(screen.queryByLabelText('Filtrer par priorité')).not.toBeInTheDocument()
    expect(gestionProjetApi.getTaches).not.toHaveBeenCalled()
  })
})
