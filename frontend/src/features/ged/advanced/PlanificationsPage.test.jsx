import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../../design/ThemeProvider.jsx'
import gedApi from '../../../api/gedApi'
import { toast } from '../../../ui'
import PlanificationsPage from './PlanificationsPage.jsx'

/* PACT137 — Planifications de document (XGED15) : échéance + assigné sur un
   document, listées (faites/à venir/en retard), créables, marquables faites.
   Mocks alignés sur `PlanificationDocumentSerializer` (id, document,
   document_nom, libelle, echeance, assigne_a, assigne_a_nom, faite,
   notifiee). Comme `CorbeillePage.test.jsx` : ListShell rend une vue table +
   une vue carte, donc toute assertion sur une cellule/action de ligne passe
   par `findAllByText`/`getAllByRole(...)`. */

vi.mock('../../../api/gedApi', () => ({
  default: {
    getPlanificationsDocument: vi.fn(),
    getDocumentsList: vi.fn(() => Promise.resolve({ data: [{ id: 4, nom: 'Bail.pdf' }] })),
    getUsers: vi.fn(() => Promise.resolve({ data: [{ id: 2, username: 'reda' }] })),
    createPlanificationDocument: vi.fn(() => Promise.resolve({ data: { id: 9 } })),
    updatePlanificationDocument: vi.fn(() => Promise.resolve({ data: {} })),
    deletePlanificationDocument: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

vi.mock('../../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn() } }
})

function renderPage() {
  return render(
    <MemoryRouter><ThemeProvider><PlanificationsPage /></ThemeProvider></MemoryRouter>,
  )
}

beforeEach(() => {
  vi.clearAllMocks()
  gedApi.getPlanificationsDocument.mockResolvedValue({
    data: [{
      id: 8, document: 4, document_nom: 'Bail.pdf', libelle: 'Relancer le locataire',
      echeance: '2020-01-15', assigne_a: 2, assigne_a_nom: 'reda', faite: false, notifiee: false,
    }],
  })
})

describe('PACT137 PlanificationsPage', () => {
  it('liste les planifications avec leur échéance et leur état', async () => {
    renderPage()
    expect((await screen.findAllByText('Relancer le locataire')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('En retard').length).toBeGreaterThan(0)
  })

  it('crée une planification sur un document', async () => {
    renderPage()
    await screen.findAllByText('Relancer le locataire')

    await userEvent.click(screen.getByRole('button', { name: /Nouvelle planification/i }))
    const dialog = await screen.findByRole('dialog')
    await userEvent.click(within(dialog).getByRole('combobox', { name: 'Choisir un document' }))
    await userEvent.click(within(await screen.findByRole('listbox')).getByText('Bail.pdf'))
    await userEvent.type(within(dialog).getByLabelText('Libellé de la planification'), 'Relancer J+7')
    fireEvent.change(within(dialog).getByLabelText('Échéance'), { target: { value: '2027-01-10' } })
    await userEvent.click(within(dialog).getByRole('button', { name: 'Créer' }))

    await waitFor(() => {
      expect(gedApi.createPlanificationDocument).toHaveBeenCalledWith({
        document: '4', libelle: 'Relancer J+7', echeance: '2027-01-10', assigne_a: undefined,
      })
      expect(toast.success).toHaveBeenCalledWith('Planification créée.')
    })
  })

  it('marque une planification faite', async () => {
    renderPage()
    await screen.findAllByText('Relancer le locataire')

    await userEvent.click(screen.getAllByRole('button', { name: 'Marquer faite' })[0])
    await waitFor(() => {
      expect(gedApi.updatePlanificationDocument).toHaveBeenCalledWith(8, { faite: true })
      expect(toast.success).toHaveBeenCalledWith('Planification marquée faite.')
    })
  })
})
