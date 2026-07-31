import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { buildProductionChartData } from './ProductionPage.jsx'

/* VX148 — ProductionPage.jsx : l'écran le plus consulté du dossier monitoring
   n'avait AUCUN graphique (juste une table de relevés) — ses 4 voisins directs
   (PR mensuel/CO2/flotte…) en ont un. `buildProductionChartData` dérive la
   tendance kWh (chronologique) des mêmes relevés que la table, testée en
   isolation (pure, sans dépendre du rendu Radix Select/ResizeObserver). */

describe('buildProductionChartData (VX148)', () => {
  it('trie les relevés par date croissante et projette {label, value}', () => {
    const readings = [
      { date: '2026-07-01', energy_kwh: '135.2' },
      { date: '2026-06-01', energy_kwh: '120.5' },
    ]
    expect(buildProductionChartData(readings)).toEqual([
      { label: '2026-06-01', value: 120.5 },
      { label: '2026-07-01', value: 135.2 },
    ])
  })

  it('ignore les relevés sans date, jamais de NaN pour une énergie invalide', () => {
    const readings = [
      { date: '2026-06-01', energy_kwh: 'abc' },
      { energy_kwh: '50' }, // pas de date
    ]
    expect(buildProductionChartData(readings)).toEqual([
      { label: '2026-06-01', value: 0 },
    ])
  })

  it('liste vide → tableau vide (le graphe retombe sur ChartEmpty)', () => {
    expect(buildProductionChartData([])).toEqual([])
    expect(buildProductionChartData(undefined)).toEqual([])
  })
})

/* WIR122 — suppression de relevé (confirmation + `deleteReading`, jusque-là
   sans appelant) + historique mensuel attendu vs réel (`getHistory`, idem). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class { observe() {} unobserve() {} disconnect() {} }
  }
})

function renderPage(ui) {
  return render(<MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>)
}

// Radix Select ne s'ouvre pas sous jsdom (portail + pointer-events:none) —
// même contournement que ClientPortalPage.test.jsx : <select> natif pour
// piloter le choix du système, les autres primitives ui/ restent réelles.
vi.mock('../../ui', async (importActual) => {
  const actual = await importActual()
  const Passthrough = ({ children }) => <>{children}</>
  return {
    ...actual,
    Select: ({ value, onValueChange, children, 'aria-label': ariaLabel }) => (
      <select
        aria-label={ariaLabel || 'select'}
        value={value}
        onChange={(e) => onValueChange(e.target.value)}
      >
        <option value="" />
        {children}
      </select>
    ),
    SelectTrigger: Passthrough,
    SelectValue: () => null,
    SelectContent: Passthrough,
    SelectItem: ({ value, children }) => <option value={value}>{children}</option>,
  }
})

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getProviders: vi.fn(() => Promise.resolve({ data: [{ key: 'noop', label: 'Aucun' }] })),
    getReadings: vi.fn(() => Promise.resolve({
      data: [{ id: 9, date: '2026-06-01', energy_kwh: '120.5', period_days: 30, source_display: 'Manuel', note: '' }],
    })),
    getConfigForInstallation: vi.fn(() => Promise.resolve({
      data: [{ id: 5, installation: 11, provider: 'noop', enabled: true }],
    })),
    deleteReading: vi.fn(() => Promise.resolve({})),
    getHistory: vi.fn(() => Promise.resolve({
      data: {
        installation: 11,
        months: 12,
        expected_annual_kwh: 12000,
        data: [{ month: '2026-06', actual_kwh: 120.5, expected_kwh: 1000, ratio_pct: 12 }],
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

// Contourne le dialogue Radix réel (déjà couvert par ui/confirm.test.jsx) —
// on vérifie ici uniquement le CÂBLAGE : confirmation → deleteReading → reload.
vi.mock('../../ui/confirm', () => ({
  useConfirmDialog: () => ({ confirmDelete: vi.fn(() => Promise.resolve(true)) }),
  toast: { success: vi.fn(), error: vi.fn() },
}))

import monitoringApi from '../../api/monitoringApi'
import ProductionPage from './ProductionPage'

describe('ProductionPage (WIR122 — suppression de relevé + historique mensuel)', () => {
  it('supprime un relevé après confirmation et recharge la liste', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    renderPage(<ProductionPage />)

    const select = await screen.findByRole('combobox', { name: 'Choisir un système installé' })
    await userEvent.selectOptions(select, '11')

    await waitFor(() => expect(monitoringApi.getReadings).toHaveBeenCalledWith({ installation: '11' }))
    // DataTable rend bureau + mobile (2 occurrences de la même valeur).
    await waitFor(() => expect(screen.getAllByText('120.5 kWh').length).toBeGreaterThan(0))

    await userEvent.click(screen.getAllByLabelText('Supprimer')[0])

    await waitFor(() => expect(monitoringApi.deleteReading).toHaveBeenCalledWith(9))
  })

  it('affiche l\'historique mensuel attendu vs réel dès qu\'une config existe', async () => {
    const { default: userEvent } = await import('@testing-library/user-event')
    renderPage(<ProductionPage />)

    const select = await screen.findByRole('combobox', { name: 'Choisir un système installé' })
    await userEvent.selectOptions(select, '11')

    await waitFor(() => expect(monitoringApi.getHistory).toHaveBeenCalledWith(5, { months: 12 }))
    expect(await screen.findByText('Historique mensuel (attendu vs réel)')).toBeInTheDocument()
    // DataTable rend bureau + mobile (2 occurrences de la même valeur).
    expect(screen.getAllByText('2026-06').length).toBeGreaterThan(0)
  })
})
