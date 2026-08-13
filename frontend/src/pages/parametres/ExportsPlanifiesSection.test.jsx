import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

/* PACT123 — Onglet « Exports planifiés » : `core.ScheduledExport` (FG383) était
   exposé sans aucun appelant frontend. Le point le plus important prouvé ici :
   sans identifiants provisionnés, l'exécution renvoie « non_configure » et
   l'écran l'AFFICHE explicitement au lieu de planter ou de mentir. */

const { get, post, patch, del } = vi.hoisted(() => ({
  get: vi.fn(), post: vi.fn(), patch: vi.fn(), del: vi.fn(),
}))
vi.mock('../../api/axios', () => ({
  default: { get, post, patch, delete: del },
}))

import ExportsPlanifiesSection from './ExportsPlanifiesSection'

const EXPORTS = [
  {
    id: 4, titre: 'Ventes du mois', dataset: 'devis', format: 'csv',
    destination: 'sftp', cron: '0 6 * * 1', actif: true,
    dernier_statut: '', derniere_execution_le: null,
  },
]
const DATASETS = [{ name: 'devis', label: 'Devis', fields: [] }]

// Les deux GET de l'écran : la liste et le catalogue de jeux de données.
function mockGets(exports_ = EXPORTS) {
  get.mockImplementation((url) => {
    if (url === '/core/saved-queries/datasets/') return Promise.resolve({ data: DATASETS })
    return Promise.resolve({ data: exports_ })
  })
}

afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderAvecRole(role) {
  const store = configureStore({ reducer: { auth: (state = { role }) => state } })
  return render(<Provider store={store}><ExportsPlanifiesSection /></Provider>)
}

describe('ExportsPlanifiesSection (PACT123)', () => {
  it('liste les exports planifiés avec un statut explicite « Jamais exécuté »', async () => {
    mockGets()
    renderAvecRole('admin')

    const ligne = await screen.findByTestId('export-planifie-4')
    expect(within(ligne).getByText('Ventes du mois')).toBeInTheDocument()
    expect(within(ligne).getByText('devis')).toBeInTheDocument()
    expect(within(ligne).getByText('CSV')).toBeInTheDocument()
    expect(within(ligne).getByText('SFTP')).toBeInTheDocument()

    const statut = screen.getByTestId('export-statut-4')
    expect(within(statut).getByText('Jamais exécuté')).toBeInTheDocument()
    expect(within(statut).getByText(/0 6 \* \* 1/)).toBeInTheDocument()
  })

  it('crée un export complet sans jamais envoyer company', async () => {
    const user = userEvent.setup()
    mockGets([])
    post.mockResolvedValue({ data: {} })
    renderAvecRole('admin')
    await screen.findByText('Aucun export planifié')

    await user.type(
      screen.getByPlaceholderText('Titre (ex. Ventes du mois vers le comptable)'),
      'Ventes du mois')
    await user.type(screen.getByPlaceholderText('Jeu de données'), 'devis')
    await user.type(
      screen.getByPlaceholderText('Planification cron (ex. 0 6 * * 1)'), '0 6 * * 1')
    await user.click(screen.getByRole('button', { name: /Créer l'export/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith('/core/scheduled-exports/', {
      titre: 'Ventes du mois', dataset: 'devis', format: 'csv',
      destination: 'sftp', cron: '0 6 * * 1',
    }))
    expect(Object.keys(post.mock.calls[0][1])).not.toContain('company')
  })

  it('affiche « Non configuré » après une exécution sans identifiants, sans planter', async () => {
    const user = userEvent.setup()
    mockGets()
    post.mockResolvedValue({
      data: {
        ...EXPORTS[0], dernier_statut: 'non_configure',
        derniere_execution_le: '2026-08-13T06:00:00Z',
      },
    })
    renderAvecRole('admin')
    await screen.findByTestId('export-planifie-4')

    await user.click(screen.getByRole('button', { name: /Exécuter maintenant/ }))

    await waitFor(() => expect(post).toHaveBeenCalledWith(
      '/core/scheduled-exports/4/executer/'))
    const statut = await screen.findByTestId('export-statut-4')
    expect(within(statut).getByText('Non configuré')).toBeInTheDocument()
    expect(within(statut).getByText(/ne sont pas encore fournis/)).toBeInTheDocument()
  })

  it("un rôle simple lit la liste mais n'a aucune commande d'écriture", async () => {
    mockGets()
    renderAvecRole('normal')

    await screen.findByTestId('export-planifie-4')
    expect(screen.queryByRole('button', { name: /Exécuter maintenant/ })).toBeNull()
    expect(screen.queryByRole('button', { name: /Créer l'export/ })).toBeNull()
  })

  it('affiche une erreur de chargement sans planter', async () => {
    get.mockRejectedValue(new Error('boom'))
    renderAvecRole('admin')
    expect(await screen.findByText(/Impossible de charger les exports planifiés/))
      .toBeInTheDocument()
  })
})
