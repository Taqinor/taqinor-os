import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import gestionProjetApi from '../../../api/gestionProjetApi'
import RessourcesPage from './RessourcesPage'

/* ZPRJ1-4 — Réglages temps société (singleton) + publier / copier-semaine /
   auto-affecter sur le lot d'affectations affiché. Toutes les actions
   passent par les endpoints serveur dédiés (jamais une mutation locale). */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getRessources: vi.fn(() => Promise.resolve({ data: [] })),
    getEquipes: vi.fn(() => Promise.resolve({ data: [] })),
    getAffectations: vi.fn(() => Promise.resolve({ data: [] })),
    getIndisponibilites: vi.fn(() => Promise.resolve({ data: [] })),
    getTimesheets: vi.fn(() => Promise.resolve({ data: [] })),
    getPlanDeCharge: vi.fn(() => Promise.resolve({ data: { lignes: [] } })),
    getReglageTemps: vi.fn(() => Promise.resolve({
      data: { id: 1, arrondi_minutes: 15, mode_arrondi: 'superieur', unite_saisie: 'heures', heures_par_jour: 8 },
    })),
    updateReglageTemps: vi.fn(() => Promise.resolve({ data: {} })),
    publierAffectations: vi.fn(() => Promise.resolve({ data: { nb_publiees: 3 } })),
    copierSemaineAffectations: vi.fn(() => Promise.resolve({ data: { nb_copiees: 2 } })),
    autoAffecter: vi.fn(() => Promise.resolve({ data: { propositions: [], nb_appliquees: 0 } })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('RessourcesPage — ZPRJ1-4', () => {
  it('ouvre les réglages temps et les enregistre', async () => {
    const user = userEvent.setup()
    render(<RessourcesPage />)
    await user.click(await screen.findByRole('button', { name: /Réglages temps/ }))
    await waitFor(() => expect(gestionProjetApi.getReglageTemps).toHaveBeenCalled())
    await user.click(await screen.findByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(gestionProjetApi.updateReglageTemps).toHaveBeenCalled())
  })

  it('« Publier » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    render(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Publier/ }))
    await waitFor(() => expect(gestionProjetApi.publierAffectations).toHaveBeenCalled())
  })

  it('« Copier la semaine » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    render(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Copier la semaine/ }))
    await waitFor(() => expect(gestionProjetApi.copierSemaineAffectations).toHaveBeenCalled())
  })

  it('« Auto-affecter » simule puis demande confirmation avant d\'appliquer', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    render(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Auto-affecter/ }))
    await waitFor(() => expect(gestionProjetApi.autoAffecter).toHaveBeenCalledWith(
      expect.any(Object), false,
    ))
    await waitFor(() => expect(gestionProjetApi.autoAffecter).toHaveBeenCalledWith(
      expect.any(Object), true,
    ))
    confirmSpy.mockRestore()
  })
})
