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

// WIR267 — registre de facturation de licence (2 factures mockées).
const FACTURES_LICENCE = [
  {
    id: 10, reference: 'LIC-2026-0001', societe_nom: 'Client Alpha',
    periode: '2026-07-01', plan_code: 'pro', montant_ttc: 1200,
    statut: 'emise', statut_libelle: 'Émise',
  },
  {
    id: 11, reference: 'LIC-2026-0002', societe_nom: 'Client Beta',
    periode: '2026-07-01', plan_code: 'starter', montant_ttc: 300,
    statut: 'payee', statut_libelle: 'Payée',
  },
]

// Routeur d'API : la console fait TROIS GET distincts (tenants + file +
// facturation de licence).
function routerGet(demandes = DEMANDES, facturesLicence = FACTURES_LICENCE) {
  return (url) => {
    if (url.startsWith('/adminops/demandes-inscription/')) {
      return Promise.resolve({ data: { results: demandes, en_attente: demandes.length } })
    }
    if (url.startsWith('/adminops/facturation-licences/')) {
      return Promise.resolve({
        data: { results: facturesLicence, total_du_ttc: 1200 },
      })
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

describe('TenantsConsole — Facturation de licence (WIR267)', () => {
  it('charge le registre et affiche le total dû TTC + les 2 factures mockées', async () => {
    renderPage()
    await waitFor(() => {
      expect(apiMock.get).toHaveBeenCalledWith(
        '/adminops/facturation-licences/', { params: undefined })
    })
    expect(screen.getByTestId('facturation-total-du')).toHaveTextContent('1200 MAD')
    expect(screen.getByText('LIC-2026-0001')).toBeInTheDocument()
    expect(screen.getByText('LIC-2026-0002')).toBeInTheDocument()
  })

  it('marque une facture payée (POST marquer-payee) et recharge le registre', async () => {
    renderPage()
    await screen.findByText('LIC-2026-0001')

    // Seule la facture « emise » (LIC-2026-0001) propose le bouton — la
    // « payee » (LIC-2026-0002) ne l'a jamais eu.
    expect(
      screen.queryByRole('button', { name: 'Marquer payée la facture LIC-2026-0002' }),
    ).not.toBeInTheDocument()

    await userEvent.click(screen.getByRole('button',
      { name: 'Marquer payée la facture LIC-2026-0001' }))

    await waitFor(() => {
      expect(apiMock.post).toHaveBeenCalledWith(
        '/adminops/facturation-licences/10/marquer-payee/', undefined)
    })
    // Le registre est rechargé après le pointage (best-effort, comme la
    // file d'inscription) : un second GET est parti.
    await waitFor(() => {
      expect(apiMock.get.mock.calls.filter(
        ([url]) => url === '/adminops/facturation-licences/',
      ).length).toBeGreaterThan(1)
    })
  })

  it('exporte le CSV (GET export-csv, blob) sans planter', async () => {
    // jsdom n'implémente pas createObjectURL/revokeObjectURL par défaut
    // (même patron que DevisList.test.jsx — QG1).
    URL.createObjectURL = vi.fn(() => 'blob:mock-url')
    URL.revokeObjectURL = vi.fn()
    const clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})

    renderPage()
    await screen.findByText('LIC-2026-0001')

    await userEvent.click(screen.getByRole('button', { name: 'Exporter CSV' }))

    await waitFor(() => {
      expect(apiMock.get).toHaveBeenCalledWith(
        '/adminops/facturation-licences/export-csv/',
        { params: undefined, responseType: 'blob' },
      )
    })
    await waitFor(() => expect(clickSpy).toHaveBeenCalled())

    clickSpy.mockRestore()
  })

  it('filtre par statut (repasse le paramètre au registre et à l’export)', async () => {
    renderPage()
    await screen.findByText('LIC-2026-0001')
    apiMock.get.mockClear()

    await userEvent.selectOptions(screen.getByLabelText('Statut'), 'payee')

    await waitFor(() => {
      expect(apiMock.get).toHaveBeenCalledWith(
        '/adminops/facturation-licences/', { params: { statut: 'payee' } })
    })
  })
})
