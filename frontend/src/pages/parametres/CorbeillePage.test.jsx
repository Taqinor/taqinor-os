import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

/* NTUX7 — écran /parametres/corbeille : moitié frontend manquante d'un
   backend `apps/trash` déjà complet (ElementSupprime, restauration par
   registre, purge planifiée NTUX29). Couvre : chargement paginé, filtres
   (type/depuis/jusqua), le toggle "Inclure les éléments restaurés", et la
   restauration (confirmation → POST → mise à jour de la ligne). */

const api = vi.hoisted(() => ({ listCorbeille: vi.fn(), restaurer: vi.fn() }))
vi.mock('../../api/trashApi', () => ({ default: api }))

const confirmMock = vi.hoisted(() => vi.fn(() => Promise.resolve(true)))
const toastError = vi.hoisted(() => vi.fn())
const toastSuccess = vi.hoisted(() => vi.fn())
vi.mock('../../ui/confirm', () => ({
  toast: { success: (...a) => toastSuccess(...a), error: (...a) => toastError(...a) },
  useConfirmDialog: () => ({ confirm: confirmMock, confirmDelete: confirmMock }),
}))

import CorbeillePage from './CorbeillePage'
import config from '../../features/parametres/module.config.jsx'

const ELEMENT = {
  id: 3, modele: 'crm.lead', type_libelle: 'Lead', libelle_snapshot: 'Ali Ben',
  supprime_par_nom: 'reda', supprime_le: '2026-08-20T10:00:00Z',
  expire_le: '2026-09-19T10:00:00Z', restaure_le: null,
}

beforeEach(() => {
  api.listCorbeille.mockResolvedValue({ data: { count: 1, results: [ELEMENT] } })
  api.restaurer.mockResolvedValue({ data: { restaure: true, element: { ...ELEMENT, restaure_le: '2026-09-01T00:00:00Z' } } })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CorbeillePage — NTUX7', () => {
  it('est routée sous /parametres ET présente dans la nav (Directeur/Admin)', () => {
    const route = config.routes.find((r) => r.path === '/parametres/corbeille')
    expect(route).toBeTruthy()
    expect(route.roles).toEqual(['responsable', 'admin'])
    const nav = config.nav.items.find((i) => i.to === '/parametres/corbeille')
    expect(nav).toBeTruthy()
    expect(nav.roles).toEqual(['responsable', 'admin'])
  })

  it('charge la première page et rend une ligne par élément supprimé', async () => {
    render(<CorbeillePage />)
    await waitFor(() => expect(api.listCorbeille).toHaveBeenCalledWith({ page: 1 }))
    const table = within(await screen.findByTestId('corbeille-table'))
    expect(table.getByText('Lead')).toBeInTheDocument()
    expect(table.getByText('Ali Ben')).toBeInTheDocument()
    expect(table.getByText('reda')).toBeInTheDocument()
    expect(table.getByRole('button', { name: 'Restaurer' })).toBeInTheDocument()
  })

  it('applique les filtres type/depuis/jusqua (jamais de société envoyée)', async () => {
    const user = userEvent.setup()
    render(<CorbeillePage />)
    await waitFor(() => expect(api.listCorbeille).toHaveBeenCalled())

    await user.type(screen.getByLabelText('Type'), 'Devis')
    await user.type(screen.getByLabelText('Supprimé depuis le'), '2026-08-01')
    await user.type(screen.getByLabelText("Jusqu'au"), '2026-08-31')
    await user.click(screen.getByRole('button', { name: 'Filtrer' }))

    await waitFor(() => expect(api.listCorbeille).toHaveBeenLastCalledWith({
      page: 1, type: 'Devis', depuis: '2026-08-01', jusqua: '2026-08-31',
    }))
    for (const appel of api.listCorbeille.mock.calls) {
      expect(appel[0]).not.toHaveProperty('company')
    }
  })

  it('« Inclure les éléments déjà restaurés » ajoute ?restaures=1', async () => {
    const user = userEvent.setup()
    render(<CorbeillePage />)
    await waitFor(() => expect(api.listCorbeille).toHaveBeenCalled())
    await user.click(screen.getByLabelText('Inclure les éléments déjà restaurés'))
    await waitFor(() => expect(api.listCorbeille).toHaveBeenLastCalledWith({ page: 1, restaures: 1 }))
  })

  it('restaurer un élément : confirme, POST, puis la ligne affiche « Restauré »', async () => {
    const user = userEvent.setup()
    render(<CorbeillePage />)
    await screen.findByTestId('corbeille-table')
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(confirmMock).toHaveBeenCalled()
    await waitFor(() => expect(api.restaurer).toHaveBeenCalledWith(3))
    await waitFor(() => expect(screen.getByText('Restauré')).toBeInTheDocument())
    expect(toastSuccess).toHaveBeenCalled()
  })

  it('restauration annulée dans la confirmation : aucun appel réseau', async () => {
    confirmMock.mockResolvedValueOnce(false)
    const user = userEvent.setup()
    render(<CorbeillePage />)
    await screen.findByTestId('corbeille-table')
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    expect(confirmMock).toHaveBeenCalled()
    expect(api.restaurer).not.toHaveBeenCalled()
  })

  it('échec de restauration (déjà restauré entre-temps) : toast avec le detail serveur', async () => {
    api.restaurer.mockRejectedValue({ response: { data: { detail: 'Cet élément a déjà été restauré.' } } })
    const user = userEvent.setup()
    render(<CorbeillePage />)
    await screen.findByTestId('corbeille-table')
    await user.click(screen.getByRole('button', { name: 'Restaurer' }))
    await waitFor(() => expect(toastError).toHaveBeenCalledWith('Cet élément a déjà été restauré.'))
  })

  it('pagine à 50 par page et charge la page suivante', async () => {
    api.listCorbeille.mockResolvedValue({ data: { count: 120, results: [ELEMENT] } })
    const user = userEvent.setup()
    render(<CorbeillePage />)
    expect(await screen.findByTestId('corbeille-pagination')).toHaveTextContent('Page 1 / 3')
    await user.click(screen.getByRole('button', { name: 'Suivant' }))
    await waitFor(() => expect(api.listCorbeille).toHaveBeenLastCalledWith({ page: 2 }))
  })

  it('corbeille vide : état vide explicite', async () => {
    api.listCorbeille.mockResolvedValue({ data: { count: 0, results: [] } })
    render(<CorbeillePage />)
    expect(await screen.findByText('Corbeille vide')).toBeInTheDocument()
  })

  it('dégrade proprement quand l’endpoint échoue', async () => {
    api.listCorbeille.mockRejectedValue(new Error('boom'))
    render(<CorbeillePage />)
    expect(await screen.findByText('Corbeille indisponible')).toBeInTheDocument()
  })
})
