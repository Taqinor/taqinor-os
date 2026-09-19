import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  list: vi.fn(),
  create: vi.fn(),
  navigate: vi.fn(),
}))

vi.mock('react-router-dom', async () => {
  const actual = await vi.importActual('react-router-dom')
  return { ...actual, useNavigate: () => mocks.navigate }
})

vi.mock('../../api/coreApi', () => ({
  default: { dossiers: { list: mocks.list, create: mocks.create } },
}))

import DossierList from './DossierList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// Patron de test de tout écran à <DataTable> (cf. features/ao/AffairesList.test.jsx).
const renderScreen = () => render(
  <MemoryRouter><ThemeProvider><DossierList /></ThemeProvider></MemoryRouter>,
)

const ROWS = [
  {
    id: 1, titre: 'Réclamation client X', type_dossier: 'reclamation_complexe',
    type_dossier_label: 'Réclamation complexe', statut: 'ouvert', statut_label: 'Ouvert',
    priorite: 'critique', priorite_label: 'Critique', proprietaire_username: 'meryem',
    echeance: '2020-01-01', liens: [{ id: 1 }], checklist: [{ id: 1, fait: true }, { id: 2, fait: false }],
  },
  {
    id: 2, titre: 'Onboarding Acme', type_dossier: 'onboarding_grand_compte',
    type_dossier_label: 'Onboarding grand compte', statut: 'en_cours', statut_label: 'En cours',
    priorite: 'normale', priorite_label: 'Normale', proprietaire_username: 'reda',
    echeance: null, liens: [], checklist: [],
  },
]

describe('DossierList (NTWFL19)', () => {
  beforeEach(() => {
    vi.clearAllMocks()
    mocks.list.mockResolvedValue({ data: ROWS })
  })

  it('affiche les dossiers avec statut/priorité/échéance', async () => {
    const { container } = renderScreen()
    await screen.findByText('Nouveau dossier')
    const table = container.querySelector('[data-dt-table]')
    expect(table).toBeTruthy()
    const row1 = within(table).getByText('Réclamation client X').closest('tr')
    expect(within(row1).getByText('Ouvert')).toBeInTheDocument()
    expect(within(row1).getByText('Critique')).toBeInTheDocument()
    expect(within(row1).getByText('En retard')).toBeInTheDocument()
    expect(within(row1).getByText('1/2')).toBeInTheDocument()

    const row2 = within(table).getByText('Onboarding Acme').closest('tr')
    expect(within(row2).getByText('En cours')).toBeInTheDocument()
  })

  it('ouvre un dossier au clic sur une ligne', async () => {
    const { container } = renderScreen()
    const table = await waitFor(() => container.querySelector('[data-dt-table]'))
    fireEvent.click(within(table).getByText('Réclamation client X'))
    expect(mocks.navigate).toHaveBeenCalledWith('/dossiers/1')
  })

  it('crée un nouveau dossier depuis la liste puis l’ouvre', async () => {
    mocks.create.mockResolvedValue({ data: { id: 99, titre: 'Nouveau litige' } })
    renderScreen()
    await screen.findByText('Nouveau dossier')
    fireEvent.click(screen.getByText('Nouveau dossier'))

    const titre = await screen.findByLabelText(/^Titre/)
    fireEvent.change(titre, { target: { value: 'Nouveau litige' } })
    fireEvent.click(screen.getByText('Créer le dossier'))

    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith(expect.objectContaining({
      titre: 'Nouveau litige',
    })))
    await waitFor(() => expect(mocks.navigate).toHaveBeenCalledWith('/dossiers/99'))
  })

  it('filtre par type de dossier (query serveur)', async () => {
    renderScreen()
    await screen.findByText('Nouveau dossier')
    mocks.list.mockClear()
    fireEvent.click(screen.getByLabelText('Filtrer par type de dossier'))
    fireEvent.click(await screen.findByText('Litige'))
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith(
      expect.objectContaining({ type_dossier: 'litige' }),
    ))
  })
})
