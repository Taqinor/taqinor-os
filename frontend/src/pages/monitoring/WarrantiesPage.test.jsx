import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

/* WR6 — L'écran garanties liste les garanties de production et, à la demande,
   rend le statut annuel (réel vs garanti dégradé) + la courbe de dégradation
   depuis /monitoring/warranties/<id>/status/ et /curve/. */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getWarranties: vi.fn(() => Promise.resolve({
      data: [{
        id: 3, installation: 11, guaranteed_year1_kwh: '14000.00',
        degradation_pct_per_year: '0.50', start_year: 2025,
        tolerance_pct: '5.00', compensation_mad_per_kwh: '1.1000', note: '',
      }],
    })),
    saveWarranty: vi.fn(() => Promise.resolve({ data: {} })),
    deleteWarranty: vi.fn(() => Promise.resolve({})),
    getWarrantyStatus: vi.fn(() => Promise.resolve({
      data: {
        has_warranty: true, year: 2026, guaranteed_kwh: '13930.00',
        actual_kwh: '12000.00', shortfall_kwh: '1930.00',
        within_tolerance: false, compensation_mad: '1357.15',
      },
    })),
    getWarrantyCurve: vi.fn(() => Promise.resolve({
      data: {
        has_warranty: true, installation: 11, threshold_pct: '5.00',
        manufacturer_recourse: true,
        points: [
          { year: 2025, guaranteed_kwh: '14000.00', actual_kwh: '13800.00', drift_pct: '1.43', anomalous: false },
          { year: 2026, guaranteed_kwh: '13930.00', actual_kwh: '12000.00', drift_pct: '13.86', anomalous: true },
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
import WarrantiesPage from './WarrantiesPage'

describe('WarrantiesPage (WR6 — garanties de production)', () => {
  it('liste les garanties avec le nom lisible du système', async () => {
    renderPage(<WarrantiesPage />)
    expect((await screen.findAllByText('INST-2026-001 — Amrani')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/14\s*000\s*kWh/).length).toBeGreaterThan(0)
  })

  it('affiche statut + courbe (recours fabricant) au clic « Statut et courbe »', async () => {
    renderPage(<WarrantiesPage />)
    await screen.findAllByText('INST-2026-001 — Amrani')

    // La DataTable rend chaque ligne en double (ligne de mesure) → on clique le 1er bouton.
    await userEvent.click(screen.getAllByRole('button', { name: 'Statut et courbe' })[0])

    const detail = await screen.findByTestId('warranty-detail')
    expect(detail).toBeInTheDocument()
    expect(await screen.findByText('Hors tolérance')).toBeInTheDocument()
    expect(screen.getByText('Compensation due')).toBeInTheDocument()
    expect(screen.getByText('Recours fabricant probable')).toBeInTheDocument()

    expect(monitoringApi.getWarrantyStatus).toHaveBeenCalledWith(3)
    expect(monitoringApi.getWarrantyCurve).toHaveBeenCalledWith(3)
  })

  it('ouvre le dialogue de création avec des champs libres (step="any")', async () => {
    renderPage(<WarrantiesPage />)
    await screen.findAllByText('INST-2026-001 — Amrani')

    await userEvent.click(screen.getByRole('button', { name: /Nouvelle garantie/ }))
    const year1 = await screen.findByLabelText('Garanti année 1 (kWh)')
    // Liberté de saisie du fondateur : jamais de snap/rejet des valeurs tapées.
    expect(year1).toHaveAttribute('step', 'any')
    expect(year1.closest('form')).toHaveProperty('noValidate', true)
  })
})
