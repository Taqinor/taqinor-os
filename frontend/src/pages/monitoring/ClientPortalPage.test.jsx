import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
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

// Radix Select ne s'ouvre pas sous jsdom (portail + pointer-events:none). On
// remplace les primitives Select par un <select> natif (les autres primitives
// de @/ui restent réelles), pour piloter le choix du client en test.
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

/* WR7 — Le portail client rend la synthèse environnementale CUMULÉE d'un client
   (production / économies / CO₂) depuis /configs/client-portal/?client=ID —
   strictement le payload backend, sans donnée interne (prix d'achat / marge). */

vi.mock('../../api/monitoringApi', () => ({
  default: {
    getClientPortal: vi.fn(() => Promise.resolve({
      data: {
        client: 7, systems_count: 2,
        total_production_kwh: '21500.00', economies_mad: '30100.00',
        co2_kg: '17415.00', co2_tonnes: '17.415',
        tarif_mad_par_kwh: '1.40', co2_kg_par_kwh: '0.81',
      },
    })),
  },
}))

vi.mock('../../api/crmApi', () => ({
  default: {
    getClients: vi.fn(() => Promise.resolve({
      data: [{ id: 7, nom: 'Société Amrani' }],
    })),
  },
}))

import monitoringApi from '../../api/monitoringApi'
import ClientPortalPage from './ClientPortalPage'

describe('ClientPortalPage (WR7 — portail environnemental client)', () => {
  it('charge un client puis rend la synthèse cumulée', async () => {
    renderPage(<ClientPortalPage />)

    // Sélection du client via le <select> natif (mock du Select) → charge le portail.
    const select = await screen.findByRole('combobox', { name: 'Choisir un client' })
    await userEvent.selectOptions(select, '7')

    await waitFor(() => expect(monitoringApi.getClientPortal).toHaveBeenCalledWith('7'))

    expect(await screen.findByText('Systèmes')).toBeInTheDocument()
    expect(screen.getByText('Production cumulée')).toBeInTheDocument()
    expect(screen.getByText('Économies estimées')).toBeInTheDocument()
    expect(screen.getByText('CO₂ évité')).toBeInTheDocument()

    // Aucune donnée interne exposée (prix d'achat / marge) — jamais rendue.
    expect(screen.queryByText(/marge/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/prix.?achat/i)).not.toBeInTheDocument()
  })
})
