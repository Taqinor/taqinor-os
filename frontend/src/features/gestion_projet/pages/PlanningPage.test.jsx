import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import PlanningPage from './PlanningPage'

/* WIR244 — le calendrier ouvré et les jours fériés n'étaient créables NULLE
   PART : le planning lisait un calendrier qu'aucun écran ne savait produire.
   Le pré-remplissage des fériés est une action SERVEUR idempotente — aucune
   date n'est fabriquée côté client. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getProjets: vi.fn(() => Promise.resolve({ data: [{ id: 10, code: 'P-1', nom: 'Villa Fès' }] })),
    getTaches: vi.fn(() => Promise.resolve({ data: [] })),
    getJalons: vi.fn(() => Promise.resolve({ data: [] })),
    getDependances: vi.fn(() => Promise.resolve({ data: [] })),
    getBaselines: vi.fn(() => Promise.resolve({ data: [] })),
    getCalendriers: vi.fn(() => Promise.resolve({ data: [] })),
    getJoursFeries: vi.fn(() => Promise.resolve({ data: [] })),
    createCalendrier: vi.fn(() => Promise.resolve({ data: { id: 4 } })),
    updateCalendrier: vi.fn(() => Promise.resolve({ data: {} })),
    createJourFerie: vi.fn(() => Promise.resolve({ data: { id: 5 } })),
    seedFeriesCalendrier: vi.fn(() => Promise.resolve({
      data: { crees: ['2026-01-01'], nb_crees: 1, nb_deja_presents: 2, fetes_mobiles_manquantes: [] },
    })),
    createDependance: vi.fn(() => Promise.resolve({ data: { id: 6 } })),
    deleteDependance: vi.fn(() => Promise.resolve({ data: {} })),
    prendreBaseline: vi.fn(() => Promise.resolve({ data: {} })),
    reprogrammerTache: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), info: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

const CALENDRIER = {
  id: 4, projet: 10, lundi: true, mardi: true, mercredi: true,
  jeudi: true, vendredi: true, samedi: false, dimanche: false, jours_feries: [],
}

async function choisirProjet(user) {
  withProviders(<PlanningPage />)
  await screen.findByRole('option', { name: /Villa Fès/ })
  await user.selectOptions(screen.getByLabelText('Projet'), '10')
  await waitFor(() => expect(gestionProjetApi.getCalendriers).toHaveBeenCalledWith({ projet: '10' }))
}

describe('PlanningPage — WIR244 : calendrier ouvré & jours fériés', () => {
  it('crée le calendrier du projet (semaine 5 jours, company serveur)', async () => {
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByRole('button', { name: /Créer le calendrier/ }))
    await waitFor(() => expect(gestionProjetApi.createCalendrier).toHaveBeenCalledWith(
      expect.objectContaining({ projet: '10', lundi: true, samedi: false, dimanche: false })))
    expect(gestionProjetApi.createCalendrier.mock.calls[0][0]).not.toHaveProperty('company')
  })

  it('ajoute un jour férié au calendrier existant', async () => {
    gestionProjetApi.getCalendriers.mockResolvedValue({ data: [CALENDRIER] })
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByRole('button', { name: /Jour férié/ }))
    const dialog = await screen.findByRole('dialog')
    fireEvent.change(within(dialog).getByLabelText(/^Date/), { target: { value: '2026-01-11' } })
    fireEvent.change(within(dialog).getByLabelText(/^Libellé/), { target: { value: 'Manifeste de l’indépendance' } })
    await user.click(within(dialog).getByRole('button', { name: 'Enregistrer' }))

    await waitFor(() => expect(gestionProjetApi.createJourFerie).toHaveBeenCalledWith(
      expect.objectContaining({ calendrier: 4 })))
  })

  it('pré-remplit les fériés via l’action serveur idempotente', async () => {
    gestionProjetApi.getCalendriers.mockResolvedValue({ data: [CALENDRIER] })
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByRole('button', { name: /Pré-remplir les fériés/ }))
    await waitFor(() => expect(gestionProjetApi.seedFeriesCalendrier).toHaveBeenCalledWith(
      4, new Date().getFullYear()))
  })

  it('bascule un jour ouvré via updateCalendrier', async () => {
    gestionProjetApi.getCalendriers.mockResolvedValue({ data: [CALENDRIER] })
    const user = userEvent.setup()
    await choisirProjet(user)

    await user.click(await screen.findByTitle('Sam — chômé'))
    await waitFor(() => expect(gestionProjetApi.updateCalendrier).toHaveBeenCalledWith(
      4, { samedi: true }))
  })
})
