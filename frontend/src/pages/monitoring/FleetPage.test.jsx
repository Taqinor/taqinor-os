import { describe, it, expect, vi, beforeAll, onTestFinished } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

// jsdom n'implémente pas ResizeObserver (mesuré par recharts ResponsiveContainer).
beforeAll(polyfillResizeObserver)

// WIR122 — drill-down CO₂ : le bouton par ligne navigue vers Co2Page avec
// `?installation=<id>` (résolu ensuite en config puis en détail CO₂).
const navigateMock = vi.fn()
vi.mock('react-router-dom', async (importOriginal) => {
  const actual = await importOriginal()
  return { ...actual, useNavigate: () => navigateMock }
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
    getDrapeaux: vi.fn(() => Promise.resolve({ data: { count: 0, results: [] } })),
    classerDrapeau: vi.fn(() => Promise.resolve({ data: {} })),
  },
}))

// ADRG47 — droit d'écriture du monitoring (`sav_gerer`, palier sav) simulé :
// vrai = porteur (Technicien) ; faux = Commercial du registre (aucun code sav).
const droit = vi.hoisted(() => ({ ecrire: true }))
vi.mock('../../features/sav/useDroitMetier', () => ({ default: () => droit.ecrire }))

import monitoringApi from '../../api/monitoringApi'
import FleetPage from './FleetPage'
import { polyfillResizeObserver } from '../../test/selectNatif'

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

  it('WIR122 — le bouton « Détail CO₂ » d\'une ligne ouvre le drill-down du système', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    renderPage(<FleetPage />)
    await screen.findByText('Systèmes actifs')

    const buttons = screen.getAllByLabelText('Détail CO₂')
    expect(buttons.length).toBeGreaterThan(0)
    await userEvent.click(buttons[0])
    expect(navigateMock).toHaveBeenCalledWith('/production/co2?installation=11')
  })

  it('ASAV116 — un système sans attendu affiche « sans référence »', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    monitoringApi.getFleet.mockResolvedValueOnce({
      data: {
        window_days: 365,
        systems_active: 2,
        total_kwc: '17.10',
        total_production_kwh: '21500.00',
        fleet_pr_pct: '95.20',
        open_alerts: 0,
        systems: [
          { installation: 11, reference: 'INST-2026-001', puissance_kwc: '9.90', production_kwh: '13200.00', pr_pct: '95.20' },
          { installation: 13, reference: 'INST-2026-003', puissance_kwc: '7.20', production_kwh: '8300.00', pr_pct: null, sans_reference: true },
        ],
      },
    })
    renderPage(<FleetPage />)
    await screen.findByText('Systèmes actifs')

    // Mode tableau : la ligne du système sans attendu lit la clé servie.
    expect((await screen.findAllByText('sans référence')).length).toBeGreaterThan(0)

    // Mode grille : le badge de la carte aussi.
    await userEvent.click(screen.getByRole('radio', { name: 'Cartes' }))
    expect((await screen.findAllByText('sans référence')).length).toBeGreaterThan(0)
    expect(screen.getAllByText(/95,2/).length).toBeGreaterThan(0)
  })

  it('AMON88 — classe une alerte ouverte avec motif', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    const { data } = await monitoringApi.getFleet()
    monitoringApi.getFleet.mockClear()
    monitoringApi.getFleet
      .mockResolvedValueOnce({ data })
      .mockResolvedValueOnce({ data: { ...data, open_alerts: 0 } })
    monitoringApi.getDrapeaux.mockResolvedValueOnce({
      data: {
        count: 1,
        results: [{
          id: 12, installation: 11, reference: 'INST-2026-001', ratio_pct: '60.00',
          date_creation: '2026-11-07T02:15:00Z', ticket: null, is_open: true,
        }],
      },
    })
    renderPage(<FleetPage />)

    await userEvent.click(await screen.findByRole('button', { name: 'Classer' }))
    const confirmer = screen.getByRole('button', { name: 'Confirmer le classement' })
    expect(confirmer).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Motif du classement'), 'Relevés en retard')
    await userEvent.click(confirmer)

    expect(monitoringApi.classerDrapeau).toHaveBeenCalledWith(12, 'Relevés en retard')
    expect(await screen.findByText('Aucune alerte de sous-performance ouverte.')).toBeInTheDocument()
    expect(screen.getByText('Aucune alerte ouverte')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Classer' })).not.toBeInTheDocument()
  })

  it('ADRG47 — un Commercial voit les alertes sans le geste « Classer »', async () => {
    droit.ecrire = false
    onTestFinished(() => { droit.ecrire = true })
    monitoringApi.getDrapeaux.mockResolvedValueOnce({
      data: { count: 1, results: [{
        id: 12, installation: 11, reference: 'INST-2026-001', ratio_pct: '60.00',
        date_creation: '2026-11-07T02:15:00Z', ticket: null, is_open: true,
      }] },
    })
    renderPage(<FleetPage />)
    expect(await screen.findByRole('region', { name: 'Alertes de sous-performance' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Classer' })).toBeNull()
  })
})
