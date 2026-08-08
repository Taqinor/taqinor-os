import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import ReglesDossierPage from './ReglesDossierPage.jsx'

/* PACT132 — Règles de dossier (XGED19) : condition simple champ/valeur,
   actions en séquence, journal des dernières exécutions. Le dépôt documentait
   lui-même ce trou comme « en attente d'arbitrage du fondateur » — cette
   tâche EST cet arbitrage. gedApi mocké : la forme des mocks (`condition_group`,
   `actions`, journal `{document_nom, declenchee, created_at}`) reproduit EXACTEMENT
   `RegleDossierSerializer`/`ExecutionRegleDossierSerializer`. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getReglesDossier: vi.fn(),
    getDossiers: vi.fn(() => Promise.resolve({ data: [{ id: 3, nom: 'Contrats' }] })),
    getTags: vi.fn(() => Promise.resolve({ data: [{ id: 1, nom: 'Urgent', slug: 'urgent' }] })),
    getUsers: vi.fn(() => Promise.resolve({ data: [{ id: 2, username: 'reda' }] })),
    createRegleDossier: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    updateRegleDossier: vi.fn(() => Promise.resolve({ data: {} })),
    deleteRegleDossier: vi.fn(() => Promise.resolve({ data: {} })),
    getExecutionsRegleDossier: vi.fn(() => Promise.resolve({ data: [] })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><ReglesDossierPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getReglesDossier.mockResolvedValue({
    data: [{
      id: 5, nom: 'Marquer urgent', folder: 3, folder_nom: 'Contrats',
      condition_group: { op: 'and', conditions: [{ field: 'nom', operator: 'contains', value: 'URGENT' }] },
      actions: [{ type: 'tag', params: { tag: 'urgent' } }],
      actif: true, ordre: 0,
    }],
  })
})

describe('PACT132 ReglesDossierPage', () => {
  it('liste les règles avec leur condition et leur nombre d’actions', async () => {
    renderPage()
    expect(await screen.findByText('Marquer urgent')).toBeInTheDocument()
    expect(screen.getAllByText(/nom contient URGENT/).length).toBeGreaterThan(0)
  })

  it('crée une règle : condition champ/valeur + une action en séquence', async () => {
    renderPage()
    await screen.findByText('Marquer urgent')

    await userEvent.click(screen.getByRole('button', { name: /Nouvelle règle/i }))
    await userEvent.click(screen.getByRole('combobox', { name: 'Choisir un dossier' }))
    await userEvent.click(await screen.findByText('Contrats'))
    await userEvent.type(screen.getByLabelText('Nom de la règle'), 'Classer les factures')
    await userEvent.type(screen.getByLabelText('Champ de la condition'), 'nom')
    await userEvent.type(screen.getByLabelText('Valeur de la condition'), 'FACTURE')

    // Action : tag "urgent".
    await userEvent.click(screen.getByRole('combobox', { name: 'Choisir un tag' }))
    await userEvent.click(await screen.findByText('Urgent'))
    await userEvent.click(screen.getByRole('button', { name: /Ajouter l'action/i }))
    expect(await screen.findByText(/Ajouter un tag — Urgent/)).toBeInTheDocument()

    await userEvent.click(screen.getByRole('button', { name: 'Créer' }))

    await waitFor(() => {
      expect(gedApi.createRegleDossier).toHaveBeenCalledWith({
        folder: '3',
        nom: 'Classer les factures',
        ordre: 0,
        condition_group: { op: 'and', conditions: [{ field: 'nom', operator: 'eq', value: 'FACTURE' }] },
        actions: [{ type: 'tag', params: { tag: 'urgent' } }],
      })
      expect(toast.success).toHaveBeenCalledWith('Règle créée.')
    })
  })

  it('désactive une règle active', async () => {
    renderPage()
    await screen.findByText('Marquer urgent')

    await userEvent.click(screen.getByRole('button', { name: 'Désactiver' }))
    await waitFor(() => {
      expect(gedApi.updateRegleDossier).toHaveBeenCalledWith(5, { actif: false })
      expect(toast.success).toHaveBeenCalledWith('Règle désactivée.')
    })
  })

  it('affiche le journal des dernières exécutions', async () => {
    gedApi.getExecutionsRegleDossier.mockResolvedValueOnce({
      data: [{ id: 71, regle: 5, document: 12, document_nom: 'Facture-0012.pdf', declenchee: true, resultats: [], created_at: '2026-08-01T09:00:00Z' }],
    })
    renderPage()
    await screen.findByText('Marquer urgent')

    await userEvent.click(screen.getByRole('button', { name: 'Journal d’exécution' }))
    expect(await screen.findByText('Facture-0012.pdf')).toBeInTheDocument()
    expect(gedApi.getExecutionsRegleDossier).toHaveBeenCalledWith(5)
  })
})
