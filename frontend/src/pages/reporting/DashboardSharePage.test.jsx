import { describe, it, expect, vi, beforeAll, beforeEach } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* XPLT10 — Partage de dashboard : liens publics tokenisés (créer/révoquer),
   `core/dashboards-partages/`.

   PACT120 — second mécanisme sur le même écran : le partage INTERNE nommé
   (`core/dashboards-partages-internes/`, modèle `DashboardPartageInterne`).
   Les charges utiles reprennent les champs RÉELS des sérialiseurs serveur
   (`DashboardPartageInterneSerializer` : id/dashboard/utilisateur/role/niveau/
   created_at/updated_at ; `UserSerializer` pour l'annuaire), jamais une forme
   inventée. */

vi.mock('../../api/coreApi', () => ({
  default: {
    dashboards: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 5, titre: 'Dashboard commercial' }],
      })),
    },
    dashboardsPartages: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 1, dashboard: 5, token: 'abc123', actif: true }],
      })),
      create: vi.fn(() => Promise.resolve({ data: {} })),
      revoke: vi.fn(() => Promise.resolve({ data: {} })),
    },
    dashboardsPartagesInternes: {
      list: vi.fn(() => Promise.resolve({
        data: [
          {
            id: 11, dashboard: 5, utilisateur: 42, role: '', niveau: 'lecture',
            created_at: '2026-08-01T09:00:00Z', updated_at: '2026-08-01T09:00:00Z',
          },
          {
            id: 12, dashboard: 5, utilisateur: null, role: 'responsable',
            niveau: 'edition',
            created_at: '2026-08-02T09:00:00Z', updated_at: '2026-08-02T09:00:00Z',
          },
        ],
      })),
      create: vi.fn(() => Promise.resolve({ data: {} })),
      update: vi.fn(() => Promise.resolve({ data: {} })),
      remove: vi.fn(() => Promise.resolve({ data: {} })),
    },
    utilisateurs: {
      list: vi.fn(() => Promise.resolve({
        data: [
          {
            id: 42, username: 'meryem', email: 'meryem@taqinor.ma',
            first_name: 'Meryem', last_name: 'B.', role_legacy: 'responsable',
            is_active: true,
          },
          {
            id: 43, username: 'sami', email: 'sami@taqinor.ma',
            first_name: '', last_name: '', role_legacy: 'normal',
            is_active: true,
          },
        ],
      })),
    },
  },
}))

import coreApi from '../../api/coreApi'
import DashboardSharePage from './DashboardSharePage'

beforeEach(() => { vi.clearAllMocks() })

describe('DashboardSharePage (XPLT10 — partage de dashboard)', () => {
  it('liste les liens de partage existants avec leur dashboard', async () => {
    renderPage(<DashboardSharePage />)

    expect((await screen.findAllByText('Dashboard commercial')).length).toBeGreaterThan(0)
    await waitFor(() => expect(coreApi.dashboardsPartages.list).toHaveBeenCalled())
  })

  it('révoquer un lien appelle dashboardsPartages.revoke', async () => {
    renderPage(<DashboardSharePage />)
    const revokeButtons = await screen.findAllByTestId('revoke-partage-1')
    revokeButtons[0].click()

    await waitFor(() => expect(coreApi.dashboardsPartages.revoke).toHaveBeenCalledWith(1))
  })
})

describe('DashboardSharePage — partage interne (PACT120)', () => {
  it('affiche les deux mécanismes distincts : liens publics ET partage interne nommé', async () => {
    renderPage(<DashboardSharePage />)

    await screen.findByTestId('partage-interne')
    // Assertions PAR LIGNE (les libellés existent aussi dans les listes
    // déroulantes du formulaire — un `getByText` global serait ambigu).
    const partageUtilisateur = screen.getByTestId('partage-interne-11')
    // Destinataire utilisateur, résolu depuis l'annuaire société.
    expect(within(partageUtilisateur).getByText('Meryem B.')).toBeInTheDocument()
    expect(within(partageUtilisateur).getByText('Lecture')).toBeInTheDocument()

    const partageRole = screen.getByTestId('partage-interne-12')
    // Destinataire rôle (le champ `role` du serveur est un texte legacy).
    expect(within(partageRole).getByText('Rôle : Utilisateur Responsable')).toBeInTheDocument()
    expect(within(partageRole).getByText('Édition')).toBeInTheDocument()
  })

  it('partage à un utilisateur choisi avec un niveau', async () => {
    const user = userEvent.setup()
    renderPage(<DashboardSharePage />)
    await screen.findByTestId('partage-interne')

    await user.selectOptions(screen.getByLabelText('Dashboard à partager'), '5')
    await user.selectOptions(screen.getByLabelText('Utilisateur'), '43')
    await user.selectOptions(screen.getByLabelText('Niveau'), 'edition')
    await user.click(screen.getByRole('button', { name: /Partager en interne/ }))

    await waitFor(() => expect(coreApi.dashboardsPartagesInternes.create)
      .toHaveBeenCalledWith({ dashboard: '5', utilisateur: '43', niveau: 'edition' }))
  })

  it('partage à un rôle choisi (aucun utilisateur envoyé)', async () => {
    const user = userEvent.setup()
    renderPage(<DashboardSharePage />)
    await screen.findByTestId('partage-interne')

    await user.selectOptions(screen.getByLabelText('Dashboard à partager'), '5')
    await user.selectOptions(screen.getByLabelText('Partager à'), 'role')
    await user.selectOptions(screen.getByLabelText('Rôle'), 'admin')
    await user.click(screen.getByRole('button', { name: /Partager en interne/ }))

    await waitFor(() => expect(coreApi.dashboardsPartagesInternes.create)
      .toHaveBeenCalledWith({ dashboard: '5', role: 'admin', niveau: 'lecture' }))
  })

  it('retire un partage interne', async () => {
    const user = userEvent.setup()
    renderPage(<DashboardSharePage />)

    await user.click(await screen.findByTestId('retirer-partage-interne-12'))
    await waitFor(() => expect(coreApi.dashboardsPartagesInternes.remove)
      .toHaveBeenCalledWith(12))
  })
})
