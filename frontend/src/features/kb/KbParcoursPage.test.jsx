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
