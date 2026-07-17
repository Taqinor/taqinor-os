// NTUX2 — bouton « Vues » : Popover listant vues perso/équipe, apply/
// dupliquer/renommer/supprimer, « Définir par défaut pour mon rôle » gated
// par permission Directeur/Admin.
import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react'

const applyViewMock = vi.fn()
const duplicateViewMock = vi.fn()
const renameViewMock = vi.fn()
const deleteViewMock = vi.fn(() => Promise.resolve())
const setDefaultForMyRoleMock = vi.fn(() => Promise.resolve())
let hookState

vi.mock('./useServerSavedViews', () => ({
  useServerSavedViews: () => hookState,
}))

const isAdminOrResponsableMock = vi.fn(() => false)
vi.mock('../../hooks/useHasPermission', () => ({
  useIsAdminOrResponsable: () => isAdminOrResponsableMock(),
}))

vi.mock('../../ui/confirm', () => ({ toast: { success: vi.fn(), error: vi.fn() } }))

import ViewsManagerPopover from './ViewsManagerPopover'
import { toast } from '../../ui/confirm'

const MINE = [{ id: 1, nom: 'Perso', est_defaut_role: false, configuration: { filtres: { a: 1 } } }]
const TEAM = [{ id: 2, nom: 'Équipe', est_defaut_role: true, configuration: {} }]

beforeEach(() => {
  vi.clearAllMocks()
  isAdminOrResponsableMock.mockReturnValue(false)
  hookState = {
    mine: MINE, team: TEAM, activeView: null, loading: false,
    applyView: applyViewMock, duplicateView: duplicateViewMock, renameView: renameViewMock,
    deleteView: deleteViewMock, setDefaultForMyRole: setDefaultForMyRoleMock,
  }
})
afterEach(() => cleanup())

describe('ViewsManagerPopover (NTUX2)', () => {
  it('ouvre le popover et liste mes vues + les vues d\'équipe', async () => {
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    expect(await screen.findByText('Perso')).toBeInTheDocument()
    expect(screen.getByText('Équipe')).toBeInTheDocument()
  })

  it('cliquer une vue l\'applique (onApply + applyView) et ferme le popover', async () => {
    const onApply = vi.fn()
    render(<ViewsManagerPopover ecran="crm.leads" onApply={onApply} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    fireEvent.click(await screen.findByText('Perso'))
    expect(applyViewMock).toHaveBeenCalledWith(MINE[0])
    expect(onApply).toHaveBeenCalledWith({ filtres: { a: 1 } })
  })

  it('« Dupliquer » appelle duplicateView avec la vue', async () => {
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    await screen.findByText('Perso')
    fireEvent.click(screen.getAllByRole('button', { name: 'Dupliquer' })[0])
    expect(duplicateViewMock).toHaveBeenCalledWith(MINE[0])
  })

  it('« Définir par défaut pour mon rôle » absent sans permission Directeur/Admin', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    await screen.findByText('Perso')
    expect(screen.queryByRole('button', { name: 'Définir par défaut pour mon rôle' })).not.toBeInTheDocument()
  })

  it('« Définir par défaut pour mon rôle » visible + fonctionnel avec permission', async () => {
    isAdminOrResponsableMock.mockReturnValue(true)
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    await screen.findByText('Perso')
    fireEvent.click(screen.getByRole('button', { name: 'Définir par défaut pour mon rôle' }))
    expect(setDefaultForMyRoleMock).toHaveBeenCalledWith(MINE[0])
    await waitFor(() => expect(toast.success).toHaveBeenCalled())
  })

  it('« Supprimer » une vue par défaut de rôle sans permission affiche une erreur, sans appeler deleteView', async () => {
    isAdminOrResponsableMock.mockReturnValue(false)
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    await screen.findByText('Équipe')
    fireEvent.click(screen.getAllByRole('button', { name: 'Supprimer' })[1])
    expect(deleteViewMock).not.toHaveBeenCalled()
    expect(toast.error).toHaveBeenCalled()
  })

  it('« Renommer » bascule en champ éditable et valide sur Entrée', async () => {
    render(<ViewsManagerPopover ecran="crm.leads" onApply={() => {}} />)
    fireEvent.click(screen.getByTestId('uxviews-open-btn'))
    await screen.findByText('Perso')
    fireEvent.click(screen.getAllByRole('button', { name: 'Renommer' })[0])
    const input = screen.getByDisplayValue('Perso')
    fireEvent.change(input, { target: { value: 'Mes leads chauds' } })
    fireEvent.keyDown(input, { key: 'Enter' })
    expect(renameViewMock).toHaveBeenCalledWith(1, 'Mes leads chauds')
  })
})
