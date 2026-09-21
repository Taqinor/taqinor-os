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

// Le toast est la seule surface où « liste tronquée » / l'erreur de création
// apparaissent ; on le mocke pour l'affirmer directement (même patron que
// FactureList.wir183.test.jsx — le barrel `ui` réexporte Toaster).
vi.mock('../../ui/Toaster', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn(), message: vi.fn(), info: vi.fn() } }
})

import DossierList from './DossierList'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { toast } from '../../ui/Toaster'

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

  it('bascule vers la vue kanban (NTWFL21)', async () => {
    const { container } = renderScreen()
    await screen.findByText('Nouveau dossier')
    fireEvent.click(screen.getByRole('radio', { name: 'Kanban' }))
    // Le tableau disparaît, les colonnes de statut apparaissent.
    expect(container.querySelector('[data-dt-table]')).toBeNull()
    expect(await screen.findByText('Ouvert', { selector: '.kb-col-title' })).toBeInTheDocument()
    expect(screen.getByText('Réclamation client X')).toBeInTheDocument()
  })

  it('filtre par priorité et « en retard uniquement » côté écran (NTWFL22)', async () => {
    const { container } = renderScreen()
    const table = await waitFor(() => container.querySelector('[data-dt-table]'))
    expect(within(table).getByText('Réclamation client X')).toBeInTheDocument()
    expect(within(table).getByText('Onboarding Acme')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Filtrer par priorité'))
    fireEvent.click(await screen.findByRole('option', { name: 'Critique' }))
    expect(within(table).getByText('Réclamation client X')).toBeInTheDocument()
    expect(within(table).queryByText('Onboarding Acme')).toBeNull()

    fireEvent.click(screen.getByText('En retard uniquement'))
    // Toujours vrai : la seule dossier « Critique » est aussi en retard.
    expect(within(table).getByText('Réclamation client X')).toBeInTheDocument()
  })

  it('enregistre une vue « Mes réclamations en retard » et la retrouve après re-rendu (NTWFL22)', async () => {
    localStorage.clear()
    vi.spyOn(window, 'prompt').mockReturnValue('Mes réclamations en retard')
    const { container, unmount } = renderScreen()
    await waitFor(() => container.querySelector('[data-dt-table]'))

    fireEvent.click(screen.getByLabelText('Filtrer par priorité'))
    fireEvent.click(await screen.findByRole('option', { name: 'Critique' }))
    fireEvent.click(screen.getByText('En retard uniquement'))
    fireEvent.click(screen.getByText('⭐ Enregistrer cette vue'))

    expect(screen.getByText('Mes réclamations en retard')).toBeInTheDocument()

    // Vue PRIVÉE (localStorage) : elle survit à un remontage de l'écran.
    unmount()
    const { container: container2 } = renderScreen()
    await waitFor(() => container2.querySelector('[data-dt-table]'))
    expect(screen.getByText('Mes réclamations en retard')).toBeInTheDocument()
  })

  it('suit `next` jusqu\'au bout : « en retard uniquement » ne perd pas un dossier de la page 2', async () => {
    const page1Item = {
      id: 1, titre: 'Dossier récent', type_dossier: 'autre', type_dossier_label: 'Autre',
      statut: 'ouvert', statut_label: 'Ouvert', priorite: 'critique', priorite_label: 'Critique',
      proprietaire_username: 'reda', echeance: '2099-01-01', liens: [], checklist: [],
    }
    const page2Item = {
      id: 2, titre: 'Dossier en retard (page 2)', type_dossier: 'litige', type_dossier_label: 'Litige',
      statut: 'ouvert', statut_label: 'Ouvert', priorite: 'critique', priorite_label: 'Critique',
      proprietaire_username: 'meryem', echeance: '2020-01-01', liens: [], checklist: [],
    }
    mocks.list.mockImplementation((params) => (params.page === 1
      ? Promise.resolve({ data: { results: [page1Item], next: 'http://x/?page=2', count: 2 } })
      : Promise.resolve({ data: { results: [page2Item], next: null, count: 2 } })))

    const { container } = renderScreen()
    const table = await waitFor(() => container.querySelector('[data-dt-table]'))
    expect(within(table).getByText('Dossier en retard (page 2)')).toBeInTheDocument()
    expect(mocks.list).toHaveBeenCalledWith(expect.objectContaining({ page: 2 }))

    // Sans suivre `next`, ce dossier (seule page 2) disparaîtrait à tort de
    // « en retard uniquement » (NTWFL22) au lieu d'y rester.
    fireEvent.click(screen.getByText('En retard uniquement'))
    expect(within(table).getByText('Dossier en retard (page 2)')).toBeInTheDocument()
    expect(within(table).queryByText('Dossier récent')).toBeNull()
  })

  it('borne la pagination à 20 pages et avertit par toast si `next` ne se termine jamais', async () => {
    mocks.list.mockImplementation((params) => Promise.resolve({
      data: {
        results: [{
          id: params.page, titre: `Dossier ${params.page}`, type_dossier: 'autre',
          type_dossier_label: 'Autre', statut: 'ouvert', statut_label: 'Ouvert',
          priorite: 'normale', priorite_label: 'Normale', proprietaire_username: 'x',
          echeance: null, liens: [], checklist: [],
        }],
        next: `http://x/?page=${params.page + 1}`, count: 9999,
      },
    }))
    const { container } = renderScreen()
    await waitFor(() => container.querySelector('[data-dt-table]'))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      expect.stringContaining('20')))
    expect(mocks.list).toHaveBeenCalledTimes(20)
  })

  it('normalise en une phrase lisible un message d\'erreur DRF renvoyé en liste', async () => {
    mocks.create.mockRejectedValueOnce({
      response: { data: { titre: ['Ce champ est obligatoire.', 'Autre souci.'] } },
    })
    renderScreen()
    await screen.findByText('Nouveau dossier')
    fireEvent.click(screen.getByText('Nouveau dossier'))
    const titre = await screen.findByLabelText(/^Titre/)
    fireEvent.change(titre, { target: { value: 'Nouveau litige' } })
    fireEvent.click(screen.getByText('Créer le dossier'))
    await waitFor(() => expect(toast.error).toHaveBeenCalledWith(
      'Ce champ est obligatoire. Autre souci.'))
  })
})
