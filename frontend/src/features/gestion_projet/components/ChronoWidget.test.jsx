import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import ChronoButton from './ChronoWidget'

/* XPRJ5 — Chrono de tâche : démarrer/arrêter. Le composant lit d'abord l'état
   du chrono actif de l'utilisateur (aucun chrono → bouton « Chrono » pour
   démarrer), puis démarre/arrête via les actions serveur dédiées. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getChronoActif: vi.fn(() => Promise.resolve({ status: 204, data: null })),
    demarrerChrono: vi.fn(() => Promise.resolve({
      data: { tache: 1, tache_libelle: 'Pose', date_debut: new Date().toISOString() },
    })),
    arreterChrono: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

const tache = { id: 1, libelle: 'Pose' }

describe('ChronoButton', () => {
  it('affiche « Chrono » quand aucun chrono actif et démarre au clic', async () => {
    const user = userEvent.setup()
    render(<ChronoButton tache={tache} />)
    const btn = await screen.findByRole('button', { name: /Chrono/ })
    await user.click(btn)
    await waitFor(() => expect(gestionProjetApi.demarrerChrono).toHaveBeenCalledWith(1))
  })

  it('affiche « Arrêter » quand le chrono actif correspond à la tâche', async () => {
    gestionProjetApi.getChronoActif.mockResolvedValueOnce({
      status: 200,
      data: { tache: 1, tache_libelle: 'Pose', date_debut: new Date().toISOString() },
    })
    render(<ChronoButton tache={tache} />)
    const btn = await screen.findByRole('button', { name: /Arrêter/ })
    const user = userEvent.setup()
    await user.click(btn)
    await waitFor(() => expect(gestionProjetApi.arreterChrono).toHaveBeenCalledWith(1))
  })
})
