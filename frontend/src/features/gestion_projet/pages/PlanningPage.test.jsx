import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import PlanningPage from './PlanningPage'

/* WIR244 — la carte « Calendrier & jours fériés » était purement lecture
   seule (calendrier, jours fériés jamais créables), et les dépendances de
   tâches (CPM) au Gantt n'étaient ni créables ni supprimables depuis l'écran.
   Ces tests couvrent les 3 créations (calendrier, jour férié, dépendance) +
   la bascule ouvré/chômé, la suppression d'un férié et le pré-remplissage
   IDEMPOTENT des fériés (seed-feries). */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getTaches: vi.fn(() => Promise.resolve({ data: [] })),
    getJalons: vi.fn(() => Promise.resolve({ data: [] })),
    getDependances: vi.fn(() => Promise.resolve({ data: [] })),
    createDependance: vi.fn(() => Promise.resolve({ data: {} })),
    deleteDependance: vi.fn(() => Promise.resolve({ data: {} })),
    getBaselines: vi.fn(() => Promise.resolve({ data: [] })),
    prendreBaseline: vi.fn(() => Promise.resolve({ data: {} })),
    getCalendriers: vi.fn(() => Promise.resolve({ data: [] })),
    createCalendrier: vi.fn(() => Promise.resolve({ data: {} })),
    updateCalendrier: vi.fn(() => Promise.resolve({ data: {} })),
    seedFeriesCalendrier: vi.fn(() => Promise.resolve({
      data: { crees: ['2026-01-01'], nb_crees: 1, nb_deja_presents: 0, fetes_mobiles_manquantes: [] },
    })),
    getJoursFeries: vi.fn(() => Promise.resolve({ data: [] })),
    createJourFerie: vi.fn(() => Promise.resolve({ data: {} })),
    deleteJourFerie: vi.fn(() => Promise.resolve({ data: {} })),
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

async function selectionnerProjet(user) {
  await screen.findByRole('option', { name: /Villa Fès/ })
  await user.selectOptions(screen.getByLabelText('Projet'), '10')
}

describe('PlanningPage — WIR244 calendrier & jours fériés', () => {
  it('« Créer le calendrier » crée un calendrier 5 jours via createCalendrier', async () => {
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('button', { name: /Créer le calendrier/ }))

    await waitFor(() => expect(gestionProjetApi.createCalendrier).toHaveBeenCalledWith({
      projet: '10',
      lundi: true, mardi: true, mercredi: true, jeudi: true, vendredi: true,
      samedi: false, dimanche: false,
    }))
  })

  it('cliquer un badge de jour appelle updateCalendrier avec la bascule', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce : `mockResolvedValue` fuit
    // au-delà de ce test (vi.clearAllMocks() efface les appels, pas les
    // implémentations), faisant réapparaître le calendrier — et son bouton
    // « Ajouter » du jour férié — dans les tests suivants.
    gestionProjetApi.getCalendriers.mockResolvedValueOnce({
      data: [{
        id: 55, projet: 10, lundi: true, mardi: true, mercredi: true, jeudi: true,
        vendredi: true, samedi: false, dimanche: false, jours_feries: [],
      }],
    })
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByTitle(/^Sam —/))

    await waitFor(() => expect(gestionProjetApi.updateCalendrier).toHaveBeenCalledWith(
      55, { samedi: true }))
  })

  it('« Ajouter » un jour férié appelle createJourFerie', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce : `mockResolvedValue` fuit
    // au-delà de ce test (vi.clearAllMocks() efface les appels, pas les
    // implémentations), faisant réapparaître le calendrier — et son bouton
    // « Ajouter » du jour férié — dans les tests suivants.
    gestionProjetApi.getCalendriers.mockResolvedValueOnce({
      data: [{
        id: 55, projet: 10, lundi: true, mardi: true, mercredi: true, jeudi: true,
        vendredi: true, samedi: false, dimanche: false, jours_feries: [],
      }],
    })
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)

    await user.type(await screen.findByLabelText('Date du jour férié'), '2026-11-06')
    await user.type(screen.getByLabelText('Libellé du jour férié'), 'Marche Verte')
    await user.click(screen.getByRole('button', { name: /Ajouter/ }))

    await waitFor(() => expect(gestionProjetApi.createJourFerie).toHaveBeenCalledWith({
      calendrier: 55, date: '2026-11-06', libelle: 'Marche Verte',
    }))
  })

  it('supprimer un jour férié appelle deleteJourFerie', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce : `mockResolvedValue` fuit
    // au-delà de ce test (vi.clearAllMocks() efface les appels, pas les
    // implémentations), faisant réapparaître le calendrier — et son bouton
    // « Ajouter » du jour férié — dans les tests suivants.
    gestionProjetApi.getCalendriers.mockResolvedValueOnce({
      data: [{
        id: 55, projet: 10, lundi: true, mardi: true, mercredi: true, jeudi: true,
        vendredi: true, samedi: false, dimanche: false, jours_feries: [],
      }],
    })
    gestionProjetApi.getJoursFeries.mockResolvedValueOnce({
      data: [{ id: 3, calendrier: 55, date: '2026-01-01', libelle: 'Jour de l’an' }],
    })
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await screen.findByText(/Jour de l’an/)

    await user.click(screen.getByLabelText('Supprimer ce jour férié'))
    await waitFor(() => expect(gestionProjetApi.deleteJourFerie).toHaveBeenCalledWith(3))
  })

  it('« Pré-remplir les fériés » appelle seedFeriesCalendrier (idempotent)', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce : `mockResolvedValue` fuit
    // au-delà de ce test (vi.clearAllMocks() efface les appels, pas les
    // implémentations), faisant réapparaître le calendrier — et son bouton
    // « Ajouter » du jour férié — dans les tests suivants.
    gestionProjetApi.getCalendriers.mockResolvedValueOnce({
      data: [{
        id: 55, projet: 10, lundi: true, mardi: true, mercredi: true, jeudi: true,
        vendredi: true, samedi: false, dimanche: false, jours_feries: [],
      }],
    })
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await user.click(await screen.findByRole('button', { name: /Pré-remplir les fériés/ }))

    await waitFor(() => expect(gestionProjetApi.seedFeriesCalendrier).toHaveBeenCalledWith(
      55, new Date().getFullYear()))
  })
})

describe('PlanningPage — WIR244 dépendances CPM (câblées depuis le Gantt)', () => {
  it('ajouter une dépendance A→B depuis le Gantt appelle createDependance et recharge', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce CHAÎNÉ deux fois (mount +
    // rechargement post-création) : `mockResolvedValue` fuirait vers le test
    // suivant du fichier (vi.clearAllMocks() n'efface pas l'implémentation).
    const tachesReponse = {
      data: [
        { id: 1, libelle: 'Étude', statut: 'termine', date_debut_prevue: '2026-01-01', date_fin_prevue: '2026-01-05' },
        { id: 2, libelle: 'Pose', statut: 'a_faire', date_debut_prevue: '2026-01-06', date_fin_prevue: '2026-01-12' },
      ],
    }
    gestionProjetApi.getTaches.mockResolvedValueOnce(tachesReponse).mockResolvedValueOnce(tachesReponse)
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await screen.findByLabelText('Diagramme de Gantt')

    await user.selectOptions(screen.getByLabelText('Tâche prédécesseur'), '1')
    await user.selectOptions(screen.getByLabelText('Tâche successeur'), '2')
    await user.click(screen.getByRole('button', { name: /Ajouter/ }))

    await waitFor(() => expect(gestionProjetApi.createDependance).toHaveBeenCalledWith({
      predecesseur: 1, successeur: 2, type_dependance: 'fs', lag: 0,
    }))
    await waitFor(() => expect(gestionProjetApi.getDependances).toHaveBeenCalledTimes(2))
  })

  it('supprimer une dépendance visible au Gantt appelle deleteDependance', async () => {
    // WIR244 (fix Fable) — mockResolvedValueOnce chaîné (mount + rechargement
    // post-suppression), jamais mockResolvedValue (fuite inter-tests).
    const tachesReponse = {
      data: [
        { id: 1, libelle: 'Étude', statut: 'termine', date_debut_prevue: '2026-01-01', date_fin_prevue: '2026-01-05' },
        { id: 2, libelle: 'Pose', statut: 'a_faire', date_debut_prevue: '2026-01-06', date_fin_prevue: '2026-01-12' },
      ],
    }
    gestionProjetApi.getTaches.mockResolvedValueOnce(tachesReponse).mockResolvedValueOnce(tachesReponse)
    const dependancesReponse = {
      data: [{ id: 7, predecesseur: 1, successeur: 2, type_dependance: 'fs', lag: 0 }],
    }
    gestionProjetApi.getDependances.mockResolvedValueOnce(dependancesReponse)
    const user = userEvent.setup()
    withProviders(<PlanningPage />)
    await selectionnerProjet(user)
    await screen.findByText(/#1 → #2/)

    await user.click(screen.getByLabelText('Supprimer la dépendance'))
    await waitFor(() => expect(gestionProjetApi.deleteDependance).toHaveBeenCalledWith(7))
  })
})
