import { describe, it, expect, vi, beforeEach } from 'vitest'
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
    // WIR250 — composition du parcours (ajout/retrait d'articles).
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

beforeEach(() => {
  // Défauts sûrs pour les appels ajoutés par WIR250.
  kbApi.listArticles.mockResolvedValue({ data: [] })
  kbApi.createParcoursArticle.mockResolvedValue({ data: { id: 1 } })
  kbApi.removeParcoursArticle.mockResolvedValue({ data: {} })
})

describe('KbParcoursPage (XKB22)', () => {
  it('liste les parcours, crée un nouveau parcours', async () => {
    kbApi.listParcours.mockResolvedValue({ data: [] })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
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
})

/* WIR250 — `createParcoursArticle`/`removeParcoursArticle` étaient exposés par
   kbApi.js sans AUCUN appelant : un parcours créé depuis cet écran restait
   VIDE À VIE, et les assignations portaient sur une séquence de zéro article.
   Ce qui est verrouillé ici : composer et décomposer le parcours depuis l'UI. */
describe('KbParcoursPage — composer le parcours (WIR250)', () => {
  const PARCOURS = { id: 5, nom: 'Onboarding commercial', actif: true }

  const ouvrirParcours = async (user, container) => {
    const row = container.querySelector('tr[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0].closest('[role="button"]')
      || screen.getAllByText('Onboarding commercial')[0]
    await user.click(row)
  }

  it('ajoute un article au parcours, à la fin de la séquence', async () => {
    kbApi.listParcours.mockResolvedValue({ data: [PARCOURS] })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
    kbApi.listAssignations.mockResolvedValue({ data: [] })
    kbApi.parcoursArticles.mockResolvedValue({
      data: [{ id: 1, article: 11, article_titre: 'Présentation entreprise', ordre: 0 }],
    })
    kbApi.listArticles.mockResolvedValue({
      data: [
        { id: 11, titre: 'Présentation entreprise' },
        { id: 12, titre: 'Sécurité chantier' },
      ],
    })

    const user = userEvent.setup()
    const { container } = render(wrap(<KbParcoursPage />))
    await waitFor(() => expect(screen.getAllByText('Onboarding commercial').length).toBeGreaterThan(0))
    await ouvrirParcours(user, container)
    await waitFor(() => expect(screen.getByText(/Présentation entreprise/)).toBeTruthy())

    // L'article DÉJÀ dans le parcours n'est pas proposé à l'ajout.
    const select = screen.getByLabelText('Article à ajouter')
    expect(select.querySelectorAll('option[value="11"]').length).toBe(0)

    await user.selectOptions(select, '12')
    await user.click(screen.getByRole('button', { name: /Ajouter au parcours/i }))

    await waitFor(() => expect(kbApi.createParcoursArticle).toHaveBeenCalledWith({
      parcours: 5, article: 12, ordre: 1,
    }))
  })

  it('retire un article du parcours', async () => {
    kbApi.listParcours.mockResolvedValue({ data: [PARCOURS] })
    messagesApi.listCompanyMembers.mockResolvedValue({ data: [] })
    kbApi.listAssignations.mockResolvedValue({ data: [] })
    kbApi.parcoursArticles.mockResolvedValue({
      data: [{ id: 1, article: 11, article_titre: 'Présentation entreprise', ordre: 0 }],
    })
    kbApi.listArticles.mockResolvedValue({ data: [{ id: 11, titre: 'Présentation entreprise' }] })

    const user = userEvent.setup()
    const { container } = render(wrap(<KbParcoursPage />))
    await waitFor(() => expect(screen.getAllByText('Onboarding commercial').length).toBeGreaterThan(0))
    await ouvrirParcours(user, container)

    await user.click(await screen.findByRole('button', {
      name: 'Retirer Présentation entreprise du parcours',
    }))
    await waitFor(() => expect(kbApi.removeParcoursArticle).toHaveBeenCalledWith(1))
  })
})
