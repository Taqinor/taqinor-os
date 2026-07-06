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

/* XPLT10 — Partage de dashboard : liens publics tokenisés (créer/révoquer),
   `core/dashboards-partages/`. */

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
  },
}))

import coreApi from '../../api/coreApi'
import DashboardSharePage from './DashboardSharePage'

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
