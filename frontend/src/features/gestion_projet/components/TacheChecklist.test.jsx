import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gestionProjetApi from '../../../api/gestionProjetApi'
import TacheChecklist from './TacheChecklist'

/* WIR246 (XPRJ14) — la checklist était morte en pratique : sur une tâche sans
   item le composant rendait `null` et aucun écran ne permettait d'en ajouter
   un — elle ne pouvait donc jamais sortir de l'état vide. */

vi.mock('../../../api/gestionProjetApi', () => ({
  default: {
    getItemsChecklist: vi.fn(() => Promise.resolve({ data: [] })),
    createItemChecklist: vi.fn(),
    deleteItemChecklist: vi.fn(() => Promise.resolve({ data: {} })),
    toggleItemChecklist: vi.fn(),
  },
}))

afterEach(() => { cleanup(); vi.clearAllMocks() })

function withProviders(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('TacheChecklist — WIR246', () => {
  it('sur une tâche vide, la saisie crée un item cochable', async () => {
    gestionProjetApi.createItemChecklist.mockResolvedValueOnce({
      data: { id: 1, tache: 5, libelle: 'Vérifier le calepinage', fait: false },
    })
    withProviders(<TacheChecklist tacheId={5} />)

    // Le champ d'ajout existe MÊME sans aucun item (plus de `return null`).
    const champ = await screen.findByLabelText('Ajouter un item')
    fireEvent.change(champ, { target: { value: 'Vérifier le calepinage' } })
    fireEvent.click(screen.getByRole('button', { name: 'Ajouter' }))

    await waitFor(() => expect(gestionProjetApi.createItemChecklist).toHaveBeenCalledWith({
      tache: 5, libelle: 'Vérifier le calepinage',
    }))
    expect(await screen.findByText('Vérifier le calepinage')).toBeInTheDocument()
    // Le corps ne porte jamais company/fait_par/fait_le (posés serveur).
    const corps = gestionProjetApi.createItemChecklist.mock.calls[0][0]
    expect(corps).not.toHaveProperty('company')
    expect(corps).not.toHaveProperty('fait_par')
  })

  it('supprime un item (optimiste) via deleteItemChecklist', async () => {
    gestionProjetApi.getItemsChecklist.mockResolvedValueOnce({
      data: [{ id: 3, tache: 5, libelle: 'Poser les rails', fait: false }],
    })
    withProviders(<TacheChecklist tacheId={5} />)
    expect(await screen.findByText('Poser les rails')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Supprimer « Poser les rails »/ }))
    await waitFor(() => expect(gestionProjetApi.deleteItemChecklist).toHaveBeenCalledWith(3))
    await waitFor(() => expect(screen.queryByText('Poser les rails')).toBeNull())
  })

  it('un refus serveur restaure l’item supprimé (rollback)', async () => {
    gestionProjetApi.getItemsChecklist.mockResolvedValueOnce({
      data: [{ id: 3, tache: 5, libelle: 'Poser les rails', fait: false }],
    })
    gestionProjetApi.deleteItemChecklist.mockRejectedValueOnce(new Error('403'))
    withProviders(<TacheChecklist tacheId={5} />)
    expect(await screen.findByText('Poser les rails')).toBeInTheDocument()

    fireEvent.click(screen.getByRole('button', { name: /Supprimer « Poser les rails »/ }))
    await waitFor(() => expect(gestionProjetApi.deleteItemChecklist).toHaveBeenCalled())
    expect(await screen.findByText('Poser les rails')).toBeInTheDocument()
  })
})
