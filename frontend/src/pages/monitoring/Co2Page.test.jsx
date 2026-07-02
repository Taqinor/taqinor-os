import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (recharts ResponsiveContainer).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

/* WR7 — Le suivi CO₂ rend les totaux parc + le tableau par système depuis
   GET /monitoring/configs/co2-fleet/. */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getCo2Fleet: vi.fn(() => Promise.resolve({
      data: {
        co2_kg_par_kwh: '0.81',
        total_production_kwh: '21500.00',
        total_co2_kg: '17415.00',
        total_co2_tonnes: '17.415',
        systems: [
          { installation: 11, reference: 'INST-2026-001', production_kwh: '13200.00', co2_kg: '10692.00', co2_tonnes: '10.692' },
          { installation: 12, reference: 'INST-2026-002', production_kwh: '8300.00', co2_kg: '6723.00', co2_tonnes: '6.723' },
        ],
      },
    })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import Co2Page from './Co2Page'

describe('Co2Page (WR7 — suivi CO₂)', () => {
  it('rend les KPI du parc et le tableau CO₂ par système', async () => {
    renderPage(<Co2Page />)
    expect(await screen.findByText('CO₂ évité (parc)')).toBeInTheDocument()
    expect(screen.getByText('Production cumulée')).toBeInTheDocument()
    expect(screen.getByText('Facteur réseau')).toBeInTheDocument()
    // Systèmes visibles (tableau + libellés du graphique).
    expect(screen.getAllByText('INST-2026-001').length).toBeGreaterThan(0)
    expect(screen.getAllByText('INST-2026-002').length).toBeGreaterThan(0)
    expect(monitoringApi.getCo2Fleet).toHaveBeenCalled()
  })
})
