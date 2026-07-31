import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (DataTable/Radix Popover MultiSelect).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WIR150 — `CampagneInnovationViewSet` (CRUD + incitation/rapport/cloner/
   tableau-bord/segments/historique/noter) n'avait aucun consommateur réel :
   seul `.incitation()` était appelé. Cet écran câble créer/lister/rapport/
   cloner. */

const {
  list, segmentsDisponibles, create, rapport, cloner,
} = vi.hoisted(() => ({
  list: vi.fn(() => Promise.resolve({
    data: [{ id: 1, nom: 'Idées pompage', statut: 'active', statut_display: 'Active', segment: ['technicien'], date_debut: '2026-07-01', date_fin: null }],
  })),
  segmentsDisponibles: vi.fn(() => Promise.resolve({ data: { results: ['technicien', 'commercial'] } })),
  create: vi.fn(() => Promise.resolve({ data: { id: 2 } })),
  rapport: vi.fn(() => Promise.resolve({
    data: { nb_utilisateurs_cibles: 5, nb_idees_proposees: 3, top_idees: [{ id: 9, titre: 'Idée A', votes_count: 4 }], taux_conversion: 0.4 },
  })),
  cloner: vi.fn(() => Promise.resolve({ data: { id: 3 } })),
}))

vi.mock('../../api/innovationApi', () => ({
  default: {
    campagnes: { list, segmentsDisponibles, create, rapport, cloner },
  },
}))

import CampagnesInnovationPage from './CampagnesInnovationPage'

beforeEach(() => { vi.clearAllMocks() })

describe('CampagnesInnovationPage (WIR150)', () => {
  it('liste les campagnes existantes', async () => {
    renderPage(<CampagnesInnovationPage />)
    // DataTable rend à la fois la table desktop et le repli carte mobile (CSS
    // seul, les deux existent dans le DOM en jsdom) : on cible le PREMIER
    // match, même patron que ModelesBcf.test.jsx / qhse.render.test.jsx.
    expect((await screen.findAllByText('Idées pompage'))[0]).toBeInTheDocument()
  })

  it('crée une campagne depuis le formulaire', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getByRole('button', { name: /Nouvelle campagne/ }))
    await user.type(screen.getByLabelText('Nom'), 'Relance O&M')
    await user.click(screen.getByRole('button', { name: 'Créer (brouillon)' }))

    await waitFor(() => expect(create).toHaveBeenCalledWith(expect.objectContaining({ nom: 'Relance O&M' })))
  })

  it('affiche le rapport d’une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Rapport' })[0])
    await waitFor(() => expect(rapport).toHaveBeenCalledWith(1))
    expect(await screen.findByText('Idée A')).toBeInTheDocument()
  })

  it('clone une campagne', async () => {
    const user = userEvent.setup()
    renderPage(<CampagnesInnovationPage />)
    await screen.findAllByText('Idées pompage')

    await user.click(screen.getAllByRole('button', { name: 'Cloner' })[0])
    await waitFor(() => expect(cloner).toHaveBeenCalledWith(1))
  })
})
