import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import migrationApi from '../../api/migrationApi'
import MigrationProjetsList from './MigrationProjetsList'

const navigate = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigate }
})

vi.mock('../../api/migrationApi', () => ({
  default: {
    listProjets: vi.fn(),
    createProjet: vi.fn(),
  },
}))

vi.mock('../../ui', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, toast: { success: vi.fn(), error: vi.fn() } }
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

function withProviders(ui) {
  return render(
    <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

describe('MigrationProjetsList (NTMIG16)', () => {
  it('affiche les projets avec leur source et leur avancement', async () => {
    migrationApi.listProjets.mockResolvedValue({
      data: [{
        id: 1, nom: 'Reprise Odoo', source: 'odoo', statut: 'chargement',
        lots_total: 3, lots_reconcilies: 1,
      }],
    })
    withProviders(<MigrationProjetsList />)

    // DataTable rend À LA FOIS la table desktop et le repli carte mobile (les
    // deux existent dans le DOM en jsdom, aucune media query n'est appliquée) :
    // on cible le premier match, même patron que RetoursProduitPage.test.jsx.
    expect((await screen.findAllByText('Reprise Odoo'))[0]).toBeTruthy()
    expect(screen.getAllByText('Odoo').length).toBeGreaterThan(0)
    expect(screen.getAllByText('1 / 3 lots')[0]).toBeTruthy()
  })

  it('affiche un état vide quand aucun projet', async () => {
    migrationApi.listProjets.mockResolvedValue({ data: { results: [] } })
    withProviders(<MigrationProjetsList />)
    expect((await screen.findAllByText(/Aucun projet de migration/i))[0]).toBeTruthy()
  })

  it('crée un projet avec la source choisie et ouvre son assistant', async () => {
    migrationApi.listProjets.mockResolvedValue({ data: [] })
    migrationApi.createProjet.mockResolvedValue({ data: { id: 42 } })
    const user = userEvent.setup()
    withProviders(<MigrationProjetsList />)

    await user.click(
      await screen.findByRole('button', { name: /Nouveau projet de migration/i }))
    await screen.findByRole('dialog')
    await user.type(screen.getByLabelText(/^Nom du projet/), 'Reprise Sage')
    await user.selectOptions(screen.getByLabelText(/^Source/), 'sage')
    await user.click(screen.getByRole('button', { name: /Créer le projet/i }))

    await waitFor(() => {
      expect(migrationApi.createProjet).toHaveBeenCalledWith(
        { nom: 'Reprise Sage', source: 'sage' })
    })
    expect(navigate).toHaveBeenCalledWith('/migration/projet/42')
  })

  it('refuse la création sans nom (aucun appel réseau)', async () => {
    migrationApi.listProjets.mockResolvedValue({ data: [] })
    const user = userEvent.setup()
    withProviders(<MigrationProjetsList />)

    await user.click(
      await screen.findByRole('button', { name: /Nouveau projet de migration/i }))
    await screen.findByRole('dialog')
    await user.click(screen.getByRole('button', { name: /Créer le projet/i }))

    expect(migrationApi.createProjet).not.toHaveBeenCalled()
  })

  it('affiche une erreur de chargement au lieu de planter', async () => {
    migrationApi.listProjets.mockRejectedValue({
      response: { data: { detail: 'Accès refusé.' } },
    })
    withProviders(<MigrationProjetsList />)
    expect(await screen.findByText(/Accès refusé\./)).toBeTruthy()
  })
})
