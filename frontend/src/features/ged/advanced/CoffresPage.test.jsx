import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import crmApi from '../../../api/crmApi'
import { toast } from '../../../ui'
import CoffresPage from './CoffresPage.jsx'

/* PACT131 — Coffres-forts documentaires (GED8) : liste (propriétaire employé
   OU client, jamais les deux), création, et consultation des documents
   classés dans un coffre. gedApi/crmApi mockés : le test vérifie que les bons
   endpoints sont appelés et que la forme des réponses réelles (`CoffreSerializer`
   : id/nom/description/proprietaire/proprietaire_nom/client/document_count)
   est respectée — jamais un champ inventé. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getCoffres: vi.fn(),
    createCoffre: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    deleteCoffre: vi.fn(() => Promise.resolve({ data: {} })),
    getCoffreDocuments: vi.fn(() => Promise.resolve({ data: [] })),
    getUsers: vi.fn(() => Promise.resolve({ data: [{ id: 2, username: 'reda' }] })),
  },
}))

vi.mock('../../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({ data: [{ id: 5, nom: 'Client Alpha' }] })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><CoffresPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getCoffres.mockResolvedValue({
    data: [
      { id: 1, nom: 'Coffre RH — Reda', description: '', proprietaire: 2, proprietaire_nom: 'reda', client: null, document_count: 3 },
      { id: 2, nom: 'Coffre Client Alpha', description: '', proprietaire: null, client: 5, document_count: 0 },
    ],
  })
  crmApi.getClients.mockResolvedValue({ data: [{ id: 5, nom: 'Client Alpha' }] })
})

describe('PACT131 CoffresPage', () => {
  it('liste les coffres avec leur propriétaire (employé ou client)', async () => {
    renderPage()
    expect((await screen.findAllByText('Coffre RH — Reda')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Employé — reda/).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/Client — Client Alpha/).length).toBeGreaterThan(0)
  })

  it('crée un coffre employé (propriétaire OU client, jamais les deux)', async () => {
    renderPage()
    await screen.findAllByText('Coffre RH — Reda')

    await userEvent.click(screen.getAllByRole('button', { name: /Nouveau coffre/i })[0])
    await userEvent.type(screen.getByLabelText('Nom du coffre'), 'Coffre Marketing')
    await userEvent.click(screen.getByRole('combobox', { name: /Choisir un employé/i }))
    await userEvent.click((await screen.findAllByText('reda'))[0])
    await userEvent.click(screen.getAllByRole('button', { name: 'Créer' })[0])

    await waitFor(() => {
      expect(gedApi.createCoffre).toHaveBeenCalledWith({
        nom: 'Coffre Marketing', description: '', proprietaire: '2', client: undefined,
      })
      expect(toast.success).toHaveBeenCalledWith('Coffre créé.')
    })
  })

  it('affiche les documents classés dans un coffre', async () => {
    gedApi.getCoffreDocuments.mockResolvedValueOnce({ data: [{ id: 41, nom: 'Contrat.pdf' }] })
    renderPage()
    await screen.findAllByText('Coffre RH — Reda')

    await userEvent.click(screen.getAllByRole('button', { name: 'Voir les documents' })[0])
    expect((await screen.findAllByText('Contrat.pdf')).length).toBeGreaterThan(0)
    expect(gedApi.getCoffreDocuments).toHaveBeenCalledWith(1)
  })
})
