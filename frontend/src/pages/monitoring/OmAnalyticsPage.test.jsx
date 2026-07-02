import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

/* WR6 — L'analytique O&M rend PR / disponibilité / dégradation + la série
   mensuelle depuis GET /monitoring/configs/<id>/om-metrics/. Avec UN SEUL
   système supervisé, il est auto-sélectionné (aucune interaction requise). */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getConfigs: vi.fn(() => Promise.resolve({
      data: [{ id: 5, installation: 11, provider: 'noop', enabled: true }],
    })),
    getOmMetrics: vi.fn(() => Promise.resolve({
      data: {
        installation: 11,
        window_days: 365,
        production_kwh: '13200.00',
        expected_kwh: '14000.00',
        pr_pct: '94.30',
        availability_pct: '88.20',
        degradation_pct_per_year: '-1.40',
        soiling_suspected: true,
        monthly_pr: [
          { month: '2026-05', kwh: '1100.00', pr_pct: '96.00' },
          { month: '2026-06', kwh: '1050.00', pr_pct: '90.10' },
        ],
      },
    })),
  },
}))

vi.mock('../../api/installationsApi', () => ({
  default: {
    getInstallations: vi.fn(() => Promise.resolve({
      data: [{ id: 11, reference: 'INST-2026-001', client_nom: 'Amrani' }],
    })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import OmAnalyticsPage from './OmAnalyticsPage'

describe('OmAnalyticsPage (WR6 — analytique O&M)', () => {
  it('auto-sélectionne le seul système et rend PR / dispo / dégradation', async () => {
    renderPage(<OmAnalyticsPage />)

    // Attendre l'auto-sélection (charge configs+parc) → appel des métriques,
    // avant d'affirmer le rendu des KPI (robuste sous charge parallèle).
    await waitFor(() => expect(monitoringApi.getOmMetrics).toHaveBeenCalled())
    expect(await screen.findByText('Performance Ratio')).toBeInTheDocument()
    expect(screen.getByText('Disponibilité')).toBeInTheDocument()
    expect(screen.getByText('Dégradation')).toBeInTheDocument()

    // Alerte de salissure suspectée (soiling_suspected: true).
    expect(screen.getByTestId('soiling-alert')).toBeInTheDocument()

    // Série mensuelle rendue (tableau + libellés de l'axe du graphique).
    expect(screen.getAllByText('2026-05').length).toBeGreaterThan(0)
    expect(screen.getAllByText('2026-06').length).toBeGreaterThan(0)

    // L'appel vise bien la CONFIG (pk du viewset), pas l'installation.
    expect(monitoringApi.getOmMetrics).toHaveBeenCalledWith('5', { window_days: 365 })
  })
})
