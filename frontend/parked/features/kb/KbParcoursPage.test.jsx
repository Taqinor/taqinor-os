import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

vi.mock('../../api/kbApi', () => ({
  default: {
    listParcours: vi.fn(),
    createParcours: vi.fn(),
    parcoursArticles: vi.fn(),
    listAssignations: vi.fn(),
    createAssignation: vi.fn(),
    assignationProgression: vi.fn(),
    // WIR250 — composition du parcours (ajout/retrait d'articles) + la liste
    // des articles chargée au montage pour peupler le sélecteur d'ajout.
    listArticles: vi.fn(),
    createParcoursArticle: vi.fn(),
    removeParcoursArticle: vi.fn(),
  },
}))
vi.mock('../../api/messagesApi', () => ({
  default: { listCompanyMembers: vi.fn() },
}))

import kbApi from '../../api/kbApi'
import messagesApi from '../../api/messagesApi'
import KbParcoursPage from './KbParcoursPage'

function wrap(ui) {
  return <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
}

describe('KbParcoursPage (XKB22)', () => {
  it('liste les parcours, crée un nouveau parcours', async () => {
    kbApi.listParcours.mockResolvedValue({ data: [] })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
    kbApi.listArticles.mockResolvedValue({ data: [] })
    kbApi.createParcours.mockResolvedValue({ data: { id: 1, nom: 'Onboarding poseur' } })
    const user = userEvent.setup()
    render(wrap(<KbParcoursPage />))

    await waitFor(() => expect(kbApi.listParcours).toHaveBeenCalled())
    await user.type(screen.getByPlaceholderText('Nom du nouveau parcours'), 'Onboarding poseur')
    await user.click(screen.getByRole('button', { name: /^Créer$/i }))
    await waitFor(() => expect(kbApi.createParcours).toHaveBeenCalledWith({ nom: 'Onboarding poseur' }))
  })

  it('ouvre un parcours, liste ses articles et assigne une personne', async () => {
    kbApi.listParcours.mockResolvedValue({
      data: [{ id: 5, nom: 'Onboarding commercial', actif: true }],
    })
    messagesApi.listCompanyMembers.mockResolvedValue({
      data: [{ id: 9, get_full_name: 'Sami Benali' }],
    })
    kbApi.listArticles.mockResolvedValue({ data: [] })
    kbApi.parcoursArticles.mockResolvedValue({
      data: [{ id: 1, article_titre: 'Présentation entreprise', ordre: 0 }],
    })
    kbApi.listAssignations.mockResolvedValue({ data: [] })
    kbApi.createAssignation.mockResolvedValue({ data: { id: 1 } })

    const user = userEvent.setup()
    const { container } = render(wrap(<KbParcoursPage />))
    await waitFor(() => expect(screen.getAllByText('Onboarding commercial').length).toBeGreaterThan(0))

    const row = container.querySelector('tr[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0].closest('[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0]
    await user.click(row)
    await waitFor(() => expect(screen.getByText(/Présentation entreprise/)).toBeTruthy())

    await user.selectOptions(screen.getByLabelText('Personne à assigner'), '9')
    await user.click(screen.getByRole('button', { name: /^Assigner$/i }))
    await waitFor(() => expect(kbApi.createAssignation).toHaveBeenCalledWith({ parcours: 5, utilisateur: 9 }))
  })

  // WIR250 — Done = « parcours composé depuis l'UI » : ajout ET retrait
  // d'un article câblés (createParcoursArticle/removeParcoursArticle),
  // jusqu'ici orphelins malgré l'API déjà exposée.
  it('ajoute un article au parcours ouvert via createParcoursArticle', async () => {
    kbApi.listParcours.mockResolvedValue({
      data: [{ id: 5, nom: 'Onboarding commercial', actif: true }],
    })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
    kbApi.listArticles.mockResolvedValue({
      data: [{ id: 42, titre: 'Procédure onduleur' }],
    })
    kbApi.parcoursArticles.mockResolvedValueOnce({ data: [] })
    kbApi.listAssignations.mockResolvedValue({ data: [] })
    kbApi.createParcoursArticle.mockResolvedValue({ data: { id: 2, parcours: 5, article: 42, ordre: 0 } })

    const user = userEvent.setup()
    const { container } = render(wrap(<KbParcoursPage />))
    await waitFor(() => expect(screen.getAllByText('Onboarding commercial').length).toBeGreaterThan(0))
    const row = container.querySelector('tr[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0].closest('[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0]
    await user.click(row)

    kbApi.parcoursArticles.mockResolvedValueOnce({
      data: [{ id: 2, parcours: 5, article: 42, article_titre: 'Procédure onduleur', ordre: 0 }],
    })
    await user.selectOptions(await screen.findByLabelText('Ajouter un article au parcours'), '42')
    await user.click(screen.getByRole('button', { name: /Ajouter un article/ }))

    await waitFor(() => expect(kbApi.createParcoursArticle).toHaveBeenCalledWith({
      parcours: 5, article: 42, ordre: 0,
    }))
    expect(await screen.findByText(/Procédure onduleur/)).toBeInTheDocument()
  })

  it('retire un article du parcours ouvert via removeParcoursArticle', async () => {
    kbApi.listParcours.mockResolvedValue({
      data: [{ id: 5, nom: 'Onboarding commercial', actif: true }],
    })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
    kbApi.listArticles.mockResolvedValue({ data: [{ id: 42, titre: 'Procédure onduleur' }] })
    kbApi.parcoursArticles.mockResolvedValue({
      data: [{ id: 2, parcours: 5, article: 42, article_titre: 'Procédure onduleur', ordre: 0 }],
    })
    kbApi.listAssignations.mockResolvedValue({ data: [] })
    kbApi.removeParcoursArticle.mockResolvedValue({ data: {} })

    const user = userEvent.setup()
    const { container } = render(wrap(<KbParcoursPage />))
    await waitFor(() => expect(screen.getAllByText('Onboarding commercial').length).toBeGreaterThan(0))
    const row = container.querySelector('tr[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0].closest('[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0]
    await user.click(row)
    await screen.findByText(/Procédure onduleur/)

    await user.click(screen.getByLabelText('Retirer cet article du parcours'))
    await waitFor(() => expect(kbApi.removeParcoursArticle).toHaveBeenCalledWith(2))
  })
})
