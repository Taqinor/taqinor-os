import { describe, it, expect, beforeEach, afterEach, vi } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

const { apiMock } = vi.hoisted(() => ({
  apiMock: { get: vi.fn(), post: vi.fn() },
}))
vi.mock('../../api/axios', () => ({ default: apiMock }))

import { MemoryRouter } from 'react-router-dom'
import TenantsConsole from './TenantsConsole'
import { ThemeProvider } from '../../design/ThemeProvider'

const TENANTS = [{
  id: 1,
  nom: 'Client Alpha',
  slug: 'client-alpha',
  statut: 'actif',
  statut_libelle: 'Actif',
  actif: true,
  plan_flag: '',
  usage: { users: 4, devis: 12, factures: 3 },
  health_score: 78,
  licences_impayees: 1,
  licences_du_ttc: 1200,
  date_creation: '2026-01-15T10:00:00Z',
}]

const DEMANDES = [{
  id: 5, societe: 'Solaire Atlas', nom: 'Karim Idrissi',
  email: 'karim@solaire-atlas.ma', statut: 'en_attente',
}]

// Routeur d'API : la console fait DEUX GET distincts (tenants + file).
function routerGet(demandes = DEMANDES) {
  return (url) => {
    if (url.startsWith('/adminops/demandes-inscription/')) {
      return Promise.resolve({ data: { results: demandes, en_attente: demandes.length } })
    }
    return Promise.resolve({ data: TENANTS })
  }
}

function renderPage() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <TenantsConsole />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

beforeEach(() => {
  apiMock.get.mockReset().mockImplementation(routerGet())
  apiMock.post.mockReset().mockResolvedValue({ data: {} })
})

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

describe('TenantsConsole — cockpit fondateur (N100/N101)', () => {
  it('affiche la table des sociétés avec santé et licences dues', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('tenants-console-table')).toBeInTheDocument()
    })
    expect(screen.getByText('Client Alpha')).toBeInTheDocument()
    expect(screen.getByText('78/100')).toBeInTheDocument()
    expect(screen.getByText('1 (1200 MAD)')).toBeInTheDocument()
  })

  it('crée un tenant et affiche le mot de passe provisoire une seule fois', async () => {
    apiMock.post.mockResolvedValue({
      data: {
        id: 2, nom: 'Installateur Nord',
        admin: { username: 'chef' },
        mot_de_passe_provisoire: 'Abcd2345Efgh6789',
      },
    })
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('tenant-creation-form')).toBeInTheDocument()
    })
    await userEvent.type(
      screen.getByLabelText('Nom de la société'), 'Installateur Nord')
    await userEvent.type(
      screen.getByLabelText("Email de l'administrateur"), 'chef@nord.ma')
    await userEvent.click(
      screen.getByRole('button', { name: 'Créer le tenant' }))

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/auth/console/tenants/creer/',
        { nom: 'Installateur Nord', email: 'chef@nord.ma' })
    })
    expect(await screen.findByTestId('mot-de-passe-provisoire'))
      .toHaveTextContent('Abcd2345Efgh6789')
  })

  it('refuse de créer sans nom ni email', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('tenant-creation-form')).toBeInTheDocument()
    })
    await userEvent.click(
      screen.getByRole('button', { name: 'Créer le tenant' }))
    expect(apiMock.post).not.toHaveBeenCalled()
    expect(screen.getByRole('alert')).toBeInTheDocument()
  })

  it('affiche la file des demandes et permet d\'approuver', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('file-demandes-inscription')).toBeInTheDocument()
    })
    await userEvent.click(screen.getByRole('button',
      { name: 'Approuver la demande de Solaire Atlas' }))
    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/adminops/demandes-inscription/5/approuver/')
    })
  })

  it('masque la file quand aucune demande n\'est en attente', async () => {
    apiMock.get.mockImplementation(routerGet([]))
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('tenants-console-table')).toBeInTheDocument()
    })
    expect(screen.queryByTestId('file-demandes-inscription')).not.toBeInTheDocument()
  })

  it('propose la demande de session support (jamais un accès direct)', async () => {
    renderPage()
    await waitFor(() => {
      expect(screen.getByTestId('tenants-console-table')).toBeInTheDocument()
    })
    const lien = screen.getByRole('link', { name: 'Demander une session' })
    expect(lien).toHaveAttribute('href', '/admin/impersonation/demander')
  })
})
