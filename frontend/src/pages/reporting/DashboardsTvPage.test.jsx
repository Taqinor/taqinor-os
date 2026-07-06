import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* XPLT10 — kiosque TV plein écran (`/dashboards-tv`, core/dashboards-tv/). */

vi.mock('../../api/coreApi', () => ({
  default: {
    dashboardsTv: {
      list: vi.fn(() => Promise.resolve({
        data: { dashboards: [{ id: 1, titre: 'Dashboard société', layout: { widgets: [] } }] },
      })),
    },
  },
}))

import coreApi from '../../api/coreApi'
import DashboardsTvPage from './DashboardsTvPage'

describe('DashboardsTvPage (XPLT10 — kiosque TV)', () => {
  it('affiche le premier dashboard partagé', async () => {
    render(<DashboardsTvPage />)

    expect(await screen.findByTestId('dashboards-tv')).toBeInTheDocument()
    expect(screen.getByText('Dashboard société')).toBeInTheDocument()
    await waitFor(() => expect(coreApi.dashboardsTv.list).toHaveBeenCalled())
  })

  it('affiche un état vide si aucun dashboard partagé', async () => {
    coreApi.dashboardsTv.list.mockResolvedValueOnce({ data: { dashboards: [] } })
    render(<DashboardsTvPage />)

    expect(await screen.findByText(/Aucun dashboard partagé/i)).toBeInTheDocument()
  })
})
