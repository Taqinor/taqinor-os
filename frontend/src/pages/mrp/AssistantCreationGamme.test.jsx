// NTMFG27 — Assistant de création de gamme opératoire (« Nouvelle gamme
// guidée »). Test e2e léger : une gamme à N opérations se crée en un seul
// flux guidé, le temps total prévisualisé est correct, l'enregistrement
// respecte l'ordre affiché. Le geste de glisser-déposer lui-même (dnd-kit,
// pointer events) n'est pas simulable en jsdom (aucun autre écran de cet
// app ne le fait) : `moveItem` — l'algorithme QUE `onDragEnd` appelle — est
// donc testé en isolation, pure et déterministe.
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const {
  getPostesCharge, createGamme, createOperationGamme,
} = vi.hoisted(() => ({
  getPostesCharge: vi.fn(() => Promise.resolve({ data: [{ id: 9, nom: 'Poste A' }] })),
  createGamme: vi.fn(() => Promise.resolve({ data: { id: 5, nom: 'Gamme test' } })),
  createOperationGamme: vi.fn(() => Promise.resolve({ data: { id: 1 } })),
}))

vi.mock('../../api/mrpApi', () => ({
  default: { getPostesCharge, createGamme, createOperationGamme },
}))

const { getProduits } = vi.hoisted(() => ({
  getProduits: vi.fn(() => Promise.resolve({
    data: { results: [{ id: 3, nom: 'Coffret AC/DC' }] },
  })),
}))

vi.mock('../../api/stockApi', () => ({ default: { getProduits } }))

import AssistantCreationGamme, { moveItem } from './AssistantCreationGamme'

function renderWizard() {
  return render(
    <MemoryRouter>
      <AssistantCreationGamme />
    </MemoryRouter>,
  )
}

beforeEach(() => { vi.clearAllMocks() })

describe('moveItem (algorithme de réordonnancement, pur)', () => {
  it('déplace un élément vers l’avant', () => {
    expect(moveItem(['a', 'b', 'c'], 2, 0)).toEqual(['c', 'a', 'b'])
  })

  it('déplace un élément vers l’arrière', () => {
    expect(moveItem(['a', 'b', 'c'], 0, 2)).toEqual(['b', 'c', 'a'])
  })

  it('ne mute jamais le tableau d’origine', () => {
    const original = ['a', 'b', 'c']
    moveItem(original, 0, 2)
    expect(original).toEqual(['a', 'b', 'c'])
  })

  it('index identique ou hors bornes -> tableau inchangé', () => {
    const original = ['a', 'b']
    expect(moveItem(original, 1, 1)).toBe(original)
    expect(moveItem(original, -1, 0)).toBe(original)
    expect(moveItem(original, 0, 5)).toBe(original)
  })
})

describe('AssistantCreationGamme (NTMFG27)', () => {
  it('bloque l’enregistrement tant qu’aucune opération n’est ajoutée', () => {
    renderWizard()
    expect(screen.getByRole('button', { name: /Enregistrer la gamme/ })).toBeDisabled()
  })

  it('ajoute une opération, prévisualise le temps total, puis enregistre en une seule '
     + 'transaction utilisateur (Gamme puis chaque OperationGamme, dans l’ordre)', async () => {
    const user = userEvent.setup()
    renderWizard()

    // Produit.
    await user.click(screen.getByRole('combobox'))
    await user.type(screen.getByRole('searchbox'), 'coffret')
    await user.click(await screen.findByRole('option', { name: /Coffret AC\/DC/ }))

    // Nom de la gamme.
    await user.type(screen.getByLabelText('Nom de la gamme'), 'Gamme standard')

    // Une opération.
    await user.click(screen.getByRole('button', { name: /Ajouter une opération/ }))
    await waitFor(() => expect(getPostesCharge).toHaveBeenCalled())
    await user.type(screen.getByPlaceholderText("Libellé de l'opération"), 'Câblage')
    await user.selectOptions(screen.getByDisplayValue('— Poste —'), '9')

    // Quantité test par défaut (1), temps prépa/unitaire par défaut (0) ->
    // aperçu correct sans saisie supplémentaire.
    expect(screen.getByText(/Temps total ≈ 0 min/)).toBeInTheDocument()

    const bouton = screen.getByRole('button', { name: /Enregistrer la gamme/ })
    expect(bouton).not.toBeDisabled()
    await user.click(bouton)

    await waitFor(() => expect(createGamme).toHaveBeenCalledWith(
      expect.objectContaining({ nom: 'Gamme standard', produit: '3' }),
    ))
    await waitFor(() => expect(createOperationGamme).toHaveBeenCalledWith(
      expect.objectContaining({ gamme: 5, ordre: 1, libelle: 'Câblage', poste_charge: '9' }),
    ))
    expect(await screen.findByText(/Gamme « Gamme test » créée avec 1 opération/)).toBeInTheDocument()
  })
})
