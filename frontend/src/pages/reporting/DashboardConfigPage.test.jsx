import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

/* WR8 — Le gestionnaire de config de tableau de bord (FG96) liste les configs
   par utilisateur / palier + la config effective, depuis
   /reporting/dashboard-config/ et /effective/. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    listDashboardConfigs: vi.fn(() => Promise.resolve({
      data: [
        { id: 1, user: null, menu_tier: 'normal', cards: ['kpis', 'ca_mensuel'] },
        { id: 2, user: 42, menu_tier: '', cards: ['pipeline'] },
      ],
    })),
    effectiveDashboardConfig: vi.fn(() => Promise.resolve({
      data: { source: 'python_default', menu_tier: 'admin', cards: ['kpis', 'pipeline'] },
    })),
    saveDashboardConfig: vi.fn(() => Promise.resolve({ data: {} })),
    deleteDashboardConfig: vi.fn(() => Promise.resolve({})),
  },
}))

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: [{ id: 42, username: 'meryem', email: 'm@taqinor.ma' }],
    })),
  },
}))

// XPLT9 — DashboardFilterBar (jusque-là construit mais jamais monté) : la
// page liste les dashboards FG381 et monte la barre de filtres pour celui
// sélectionné.
vi.mock('../../api/coreApi', () => ({
  default: {
    dashboards: {
      list: vi.fn(() => Promise.resolve({
        data: [{ id: 7, titre: 'Dashboard commercial', layout: { widgets: [] } }],
      })),
      updateLayout: vi.fn(() => Promise.resolve({ data: {} })),
    },
  },
}))

import reportingApi from '../../api/reportingApi'
import coreApi from '../../api/coreApi'
import DashboardConfigPage from './DashboardConfigPage'

describe('DashboardConfigPage (WR8 — config tableaux de bord)', () => {
  it('rend la config effective + les configs par palier/utilisateur', async () => {
    renderPage(<DashboardConfigPage />)

    // Bloc config effective de l'utilisateur courant.
    expect(await screen.findByTestId('effective-config')).toBeInTheDocument()

    // Les deux configs listées (palier normal + utilisateur meryem via user id).
    expect(screen.getAllByText('Palier de rôle').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Utilisateur').length).toBeGreaterThan(0)
    expect(screen.getAllByText('meryem').length).toBeGreaterThan(0)

    await waitFor(() => expect(reportingApi.listDashboardConfigs).toHaveBeenCalled())
    expect(reportingApi.effectiveDashboardConfig).toHaveBeenCalled()
  })

  it('XPLT9 — monte DashboardFilterBar une fois un dashboard choisi', async () => {
    renderPage(<DashboardConfigPage />)

    await waitFor(() => expect(coreApi.dashboards.list).toHaveBeenCalled())
    expect(screen.queryByTestId('dashboard-filter-bar')).not.toBeInTheDocument()

    const select = await screen.findByLabelText('Choisir un tableau de bord')
    select.click()
    const option = await screen.findByText('Dashboard commercial')
    option.click()

    expect(await screen.findByTestId('dashboard-filter-bar')).toBeInTheDocument()
  })
})
