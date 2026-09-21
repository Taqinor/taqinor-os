import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import TempsPage from './TempsPage'

/* XPRJ6 — Grille hebdomadaire de saisie des temps : smoke test (rendu +
   sélection de ressource déclenche le chargement de la grille) et bouton
   « copier la semaine précédente » (appelle l'action serveur dédiée, jamais
   une auto-saisie). Toutes les données `gestionProjetApi` sont mockées. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getRessources: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Amine' }] })),
    getGrilleSemaineTemps: vi.fn(() => Promise.resolve({
      data: {
        debut_semaine: '2026-01-05',
        fin_semaine: '2026-01-11',
        jours: ['2026-01-05', '2026-01-06', '2026-01-07', '2026-01-08', '2026-01-09', '2026-01-10', '2026-01-11'],
        lignes: [{
          projet: 10, projet_code: 'P-1', tache: 20, tache_libelle: 'Pose',
          heures: ['4', '0', '0', '0', '0', '0', '0'], total_ligne: '4',
        }],
        total_par_jour: ['4', '0', '0', '0', '0', '0', '0'],
        total_semaine: '4',
        suggestions: [],
      },
    })),
    createTimesheet: vi.fn(() => Promise.resolve({ data: {} })),
    copierSemaineTimesheets: vi.fn(() => Promise.resolve({
      data: { nb_copiees: 2, nb_sautees: 0, copiees: [], sautees: [] },
    })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TempsPage', () => {
  it('affiche un état vide sans ressource sélectionnée', async () => {
    render(<TempsPage />)
    expect(await screen.findByText('Aucune ressource sélectionnée')).toBeInTheDocument()
  })

  it('charge la grille après sélection d’une ressource', async () => {
    const user = userEvent.setup()
    render(<TempsPage />)
    await waitFor(() => expect(gestionProjetApi.getRessources).toHaveBeenCalled())
    await screen.findByRole('option', { name: 'Amine' })
    await user.selectOptions(screen.getByLabelText('Ressource'), '1')
    await waitFor(() => expect(gestionProjetApi.getGrilleSemaineTemps).toHaveBeenCalledWith(
      expect.objectContaining({ ressource: '1' }),
    ))
    expect(await screen.findByText('P-1')).toBeInTheDocument()
    expect(screen.getByText('Pose')).toBeInTheDocument()
  })

  it('le bouton « copier la semaine précédente » appelle le service dédié', async () => {
    const user = userEvent.setup()
    render(<TempsPage />)
    await waitFor(() => expect(gestionProjetApi.getRessources).toHaveBeenCalled())
    await screen.findByRole('option', { name: 'Amine' })
    await user.selectOptions(screen.getByLabelText('Ressource'), '1')
    await screen.findByText('P-1')
    await user.click(screen.getByRole('button', { name: /Copier la semaine précédente/ }))
    await waitFor(() => expect(gestionProjetApi.copierSemaineTimesheets).toHaveBeenCalledWith(
      expect.objectContaining({ ressource: '1' }),
    ))
  })
})
