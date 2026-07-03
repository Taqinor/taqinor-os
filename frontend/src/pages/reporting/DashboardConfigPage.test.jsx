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

import reportingApi from '../../api/reportingApi'
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
})
