import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
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
    // PACT22 — forme réelle de services.auto_affecter : {simule, deplacements,
    // creations, non_resolues} — jamais `propositions`/`nb_propositions`/
    // `nb_appliquees`, qui n'ont jamais existé côté serveur.
    autoAffecter: vi.fn(() => Promise.resolve({
      data: { simule: true, deplacements: [], creations: [], non_resolues: [] },
    })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

import { toast } from '../../../ui'

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('RessourcesPage — ZPRJ1-4', () => {
  it('ouvre les réglages temps et les enregistre', async () => {
    const user = userEvent.setup()
    withProviders(<RessourcesPage />)
    await user.click(await screen.findByRole('button', { name: /Réglages temps/ }))
    await waitFor(() => expect(gestionProjetApi.getReglageTemps).toHaveBeenCalled())
    await user.click(await screen.findByRole('button', { name: 'Enregistrer' }))
    await waitFor(() => expect(gestionProjetApi.updateReglageTemps).toHaveBeenCalled())
  })

  it('« Publier » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    withProviders(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Publier/ }))
    await waitFor(() => expect(gestionProjetApi.publierAffectations).toHaveBeenCalled())
  })

  it('« Copier la semaine » appelle l\'action serveur dédiée', async () => {
    const user = userEvent.setup()
    withProviders(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Copier la semaine/ }))
    await waitFor(() => expect(gestionProjetApi.copierSemaineAffectations).toHaveBeenCalled())
  })

  it('« Auto-affecter » simule puis demande confirmation avant d\'appliquer', async () => {
    const user = userEvent.setup()
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    withProviders(<RessourcesPage />)
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

  it('PACT22 — le message d\'après-confirmation utilise le décompte APPLIQUÉ, jamais le décompte SIMULÉ', async () => {
    const user = userEvent.setup()
    // Simulation (confirmer=false) : 1 déplacement + 1 création proposés,
    // 1 tâche non résolue. Application (confirmer=true) : la réponse RÉELLE
    // n'a que 2 créations (déplacement retombé caduc, cas volontairement
    // DIFFÉRENT du chiffre simulé) pour prouver que le message n'affiche
    // jamais le nombre simulé comme s'il avait été appliqué.
    gestionProjetApi.autoAffecter
      .mockResolvedValueOnce({
        data: {
          simule: true,
          deplacements: [{ affectation: 1, vers_ressource: 2 }],
          creations: [{ tache: 10, ressource: 2 }],
          non_resolues: [{ tache: 99, tache_libelle: 'Sans ressource' }],
        },
      })
      .mockResolvedValueOnce({
        data: {
          simule: false,
          deplacements: [],
          creations: [{ tache: 10, ressource: 2 }, { tache: 11, ressource: 3 }],
          non_resolues: [],
        },
      })
    const confirmSpy = vi.spyOn(window, 'confirm').mockReturnValue(true)
    withProviders(<RessourcesPage />)
    await user.click(await screen.findByRole('tab', { name: 'Affectations' }))
    await user.click(await screen.findByRole('button', { name: /Auto-affecter/ }))

    await waitFor(() => expect(confirmSpy).toHaveBeenCalledWith(
      expect.stringContaining('2 proposition(s) d\'affectation SIMULÉE(S)'),
    ))
    expect(confirmSpy).toHaveBeenCalledWith(expect.stringContaining('1 tâche(s)'))

    await waitFor(() => expect(toast.success).toHaveBeenCalledWith(
      expect.stringContaining('2 affectation(s) APPLIQUÉE(S)'),
    ))
    // Jamais le chiffre simulé (2 déplacements/créations dont 1 déplacement)
    // affiché comme si le déplacement avait été appliqué.
    expect(toast.success).not.toHaveBeenCalledWith(expect.stringContaining('non résolue(s))'))

    confirmSpy.mockRestore()
  })
})
