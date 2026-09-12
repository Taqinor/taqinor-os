import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTUX27 — écran /parametres/ux : moitié frontend d'un backend
   `apps.uxviews.UxParametres` déjà complet (singleton société, GET/PATCH
   `/uxviews/parametres/`). Couvre : chargement + pré-remplissage, bascule du
   partage d'équipe, retrait d'un rôle autorisé pré-sélectionné (MultiSelect),
   et le PATCH final avec le formulaire complet. */

const api = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('../../api/axios', () => ({ default: api }))

const getRoles = vi.hoisted(() => vi.fn())
vi.mock('../../api/rolesApi', () => ({ default: { getRoles: (...a) => getRoles(...a) } }))

const toastError = vi.hoisted(() => vi.fn())
const toastSuccess = vi.hoisted(() => vi.fn())
vi.mock('../../ui/confirm', () => ({
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
}))

import UxParametresPage from './UxParametresPage'
import config from '../../features/parametres/module.config.jsx'

const PARAMS = {
  duree_hover_peek_ms: 400, duree_undo_toast_s: 10,
  permettre_vues_partagees_equipe: true,
  roles_autorises_definir_defaut: [1],
  max_vues_par_utilisateur: 50, max_favoris_par_utilisateur: 30,
}
const ROLES = [{ id: 1, nom: 'Directeur' }, { id: 2, nom: 'Commercial' }]

beforeEach(() => {
  api.get.mockReset().mockResolvedValue({ data: PARAMS })
  api.patch.mockReset().mockResolvedValue({ data: PARAMS })
  getRoles.mockReset().mockResolvedValue({ data: ROLES })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('UxParametresPage — NTUX27', () => {
  it('est routée sous /parametres ET présente dans la nav (Directeur/Admin)', () => {
    const route = config.routes.find((r) => r.path === '/parametres/ux')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])
    const nav = config.nav.items.find((i) => i.to === '/parametres/ux')
    expect(nav).toBeTruthy()
    expect(nav.roles).toEqual(['responsable', 'admin'])
  })

  it('charge et pré-remplit les réglages + le rôle déjà autorisé', async () => {
    render(<UxParametresPage />)
    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/uxviews/parametres/'))
    expect(await screen.findByDisplayValue('400')).toBeInTheDocument()
    expect(screen.getByDisplayValue('10')).toBeInTheDocument()
    expect(screen.getByDisplayValue('50')).toBeInTheDocument()
    expect(screen.getByDisplayValue('30')).toBeInTheDocument()
    // MultiSelect affiche le jeton du rôle pré-sélectionné SANS ouvrir le popover.
    expect(screen.getByText('Directeur')).toBeInTheDocument()
  })

  it('enregistrer envoie un PATCH avec le formulaire complet', async () => {
    const user = userEvent.setup()
    render(<UxParametresPage />)
    await screen.findByDisplayValue('400')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(api.patch).toHaveBeenCalledWith('/uxviews/parametres/', PARAMS))
    expect(toastSuccess).toHaveBeenCalled()
  })

  it('désactiver le partage d\'équipe puis enregistrer envoie false', async () => {
    const user = userEvent.setup()
    render(<UxParametresPage />)
    await screen.findByDisplayValue('400')
    await user.click(screen.getByLabelText("Autoriser les vues partagées d'équipe"))
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(api.patch).toHaveBeenLastCalledWith('/uxviews/parametres/', {
      ...PARAMS, permettre_vues_partagees_equipe: false,
    }))
  })

  it('retirer le rôle pré-sélectionné (jeton MultiSelect) vide la liste au PATCH', async () => {
    const user = userEvent.setup()
    render(<UxParametresPage />)
    await screen.findByDisplayValue('400')
    await user.click(screen.getByRole('button', { name: 'Retirer Directeur' }))
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(api.patch).toHaveBeenLastCalledWith('/uxviews/parametres/', {
      ...PARAMS, roles_autorises_definir_defaut: [],
    }))
  })

  it('modifier le seuil de vues max avant enregistrement', async () => {
    const user = userEvent.setup()
    render(<UxParametresPage />)
    await screen.findByDisplayValue('400')
    const champ = screen.getByLabelText('Nombre maximum de vues personnelles par utilisateur')
    await user.clear(champ)
    await user.type(champ, '75')
    await user.click(screen.getByRole('button', { name: /Enregistrer/ }))
    await waitFor(() => expect(api.patch).toHaveBeenLastCalledWith('/uxviews/parametres/', {
      ...PARAMS, max_vues_par_utilisateur: '75',
    }))
  })

  it('échec du chargement : toast, jamais un crash', async () => {
    api.get.mockRejectedValue(new Error('boom'))
    render(<UxParametresPage />)
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Chargement des réglages UX impossible.'))
  })
})
