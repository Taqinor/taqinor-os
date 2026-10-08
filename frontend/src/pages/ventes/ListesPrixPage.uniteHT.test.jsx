// AGNR10 — l'unité de saisie d'une liste de prix est HT (contrat prix_applicable.json).
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, fireEvent, within } from '@testing-library/react'

vi.mock('../../api/ventesApi', () => ({
  default: {
    getListesPrix: vi.fn(),
    getListePrix: vi.fn(),
    createListePrix: vi.fn(),
    setLignePrixListe: vi.fn(),
    addRegleListePrix: vi.fn(),
    patchListePrix: vi.fn(),
    deleteListePrix: vi.fn(),
  },
}))
vi.mock('../../api/stockApi', () => ({
  default: { getProduits: vi.fn(() => Promise.resolve({ data: [] })) },
}))

import ventesApi from '../../api/ventesApi'
import ListesPrixPage from './ListesPrixPage'

beforeEach(() => vi.clearAllMocks())

describe('ListesPrixPage — unité HT', () => {
  it("le champ prix se libelle « Prix unitaire HT » avec l'aide de conversion", async () => {
    const liste = { id: 1, nom: 'Revendeur', devise: 'MAD', archived: false, lignes: [], regles: [] }
    ventesApi.getListesPrix.mockResolvedValue({ data: [liste] })
    ventesApi.getListePrix.mockResolvedValue({ data: liste })
    render(<ListesPrixPage />)
    fireEvent.click(await screen.findByText('Revendeur'))
    const dialog = await screen.findByRole('dialog')
    fireEvent.click(within(dialog).getByRole('button', { name: /Ajouter un prix/ }))
    const dialogs = await screen.findAllByRole('dialog')
    const add = dialogs[dialogs.length - 1]
    expect(within(add).getByLabelText(/Prix unitaire HT/)).toBeInTheDocument()
    expect(within(add).queryByText(/TTC\/HT selon mode/)).toBeNull()
    expect(within(add).getByText(/convertit au taux de chaque ligne/)).toBeInTheDocument()
  })
})
