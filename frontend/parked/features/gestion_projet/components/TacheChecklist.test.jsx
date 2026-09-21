import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import TacheChecklist from './TacheChecklist'

/* WIR246 — la checklist était morte en pratique : `return null` dès que la
   tâche n'avait aucun item, sans aucun moyen d'en créer un. Ces tests
   couvrent la ligne « Ajouter un item » (createItemChecklist) toujours
   visible (même à vide) et la suppression optimiste + rollback serveur. */

const mocks = vi.hoisted(() => ({
  getItemsChecklist: vi.fn(),
  createItemChecklist: vi.fn(),
  deleteItemChecklist: vi.fn(),
  toggleItemChecklist: vi.fn(),
}))

vi.mock('../../../api/gestionProjetApi', () => ({ default: mocks }))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TacheChecklist', () => {
  it('reste visible et propose « Ajouter un item » même sans aucun item (WIR246)', async () => {
    mocks.getItemsChecklist.mockResolvedValue({ data: [] })
    render(<TacheChecklist tacheId={42} />)
    expect(await screen.findByLabelText('Nouvel item de checklist')).toBeInTheDocument()
    expect(screen.getByLabelText('Ajouter un item')).toBeDisabled()
  })

  it('« Ajouter un item » crée l\'item via createItemChecklist puis l\'affiche', async () => {
    mocks.getItemsChecklist.mockResolvedValue({ data: [] })
    mocks.createItemChecklist.mockResolvedValue({
      data: { id: 9, tache: 42, libelle: 'Vérifier onduleur', fait: false },
    })
    const user = userEvent.setup()
    render(<TacheChecklist tacheId={42} />)
    const input = await screen.findByLabelText('Nouvel item de checklist')
    await user.type(input, 'Vérifier onduleur')
    await user.click(screen.getByLabelText('Ajouter un item'))
    await waitFor(() => expect(mocks.createItemChecklist).toHaveBeenCalledWith({
      tache: 42, libelle: 'Vérifier onduleur',
    }))
    expect(await screen.findByText('Vérifier onduleur')).toBeInTheDocument()
    expect(input).toHaveValue('')
  })

  it('supprime un item de façon optimiste puis restaure en cas d\'échec serveur', async () => {
    mocks.getItemsChecklist.mockResolvedValue({
      data: [{ id: 1, tache: 42, libelle: 'Item A', fait: false }],
    })
    mocks.deleteItemChecklist.mockRejectedValue(new Error('boom'))
    const user = userEvent.setup()
    render(<TacheChecklist tacheId={42} />)
    expect(await screen.findByText('Item A')).toBeInTheDocument()
    await user.click(screen.getByLabelText('Supprimer « Item A »'))
    await waitFor(() => expect(mocks.deleteItemChecklist).toHaveBeenCalledWith(1))
    // Le serveur a refusé la suppression : l'item est restauré (rollback).
    expect(await screen.findByText('Item A')).toBeInTheDocument()
  })
})
