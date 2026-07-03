import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par recharts ResponsiveContainer).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

// DataTable lit la densité via useDensity → <ThemeProvider> ; MemoryRouter pour NavLink.
function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WR6 — La vue parc rend les KPI flotte + le tableau des systèmes depuis les
   données LIVE de GET /monitoring/configs/fleet/ (mocké ici). */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getFleet: vi.fn(() => Promise.resolve({
      data: {
        window_days: 365,
        systems_active: 2,
        total_kwc: '17.10',
        total_production_kwh: '21500.00',
        fleet_pr_pct: '91.30',
        open_alerts: 1,
        systems: [
          { installation: 11, reference: 'INST-2026-001', puissance_kwc: '9.90', production_kwh: '13200.00', pr_pct: '95.20' },
          { installation: 12, reference: 'INST-2026-002', puissance_kwc: '7.20', production_kwh: '8300.00', pr_pct: '72.10' },
        ],
      },
    })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import FleetPage from './FleetPage'

describe('FleetPage (WR6 — vue parc)', () => {
  it('rend les KPI du parc et le tableau des systèmes', async () => {
    renderPage(<FleetPage />)

    // KPI depuis le payload fleet_overview.
    expect(await screen.findByText('Systèmes actifs')).toBeInTheDocument()
    expect(screen.getByText('Puissance installée')).toBeInTheDocument()
    expect(screen.getByText('PR parc')).toBeInTheDocument()
    expect(screen.getByText(/1 alerte\(s\) de sous-performance/)).toBeInTheDocument()

    // Les deux systèmes du parc apparaissent (tableau + libellés du graphique).
    expect(screen.getAllByText('INST-2026-001').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INST-2026-002').length).toBeGreaterThan(0)

    expect(monitoringApi.getFleet).toHaveBeenCalledWith({ window_days: 365 })
  })

  it('recharge avec la fenêtre choisie (90 j)', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    renderPage(<FleetPage />)
    await screen.findByText('Systèmes actifs')

    await userEvent.click(screen.getByRole('radio', { name: '90 j' }))
    expect(monitoringApi.getFleet).toHaveBeenCalledWith({ window_days: 90 })
  })
})
