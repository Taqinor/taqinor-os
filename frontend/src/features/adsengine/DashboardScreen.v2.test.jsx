import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* ADSDEEP61 — Dashboard v2 : tuiles ADDITIVES conversations WhatsApp réelles +
   MER mixte (dépense Meta vs CA signé Odoo, DEUX devises JAMAIS fusionnées),
   chacune avec une sparkline 14 j. L'endpoint est optionnel : un mock de
   `metrics` sans `dashboardV2` (autres suites de ce fichier) ne doit rien
   casser (garde `?.` côté écran). */

const mocks = vi.hoisted(() => ({
  dashboard: vi.fn(),
  dashboardV2: vi.fn(),
  leads: vi.fn(),
  alerts: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    metrics: { dashboard: mocks.dashboard, dashboardV2: mocks.dashboardV2, leads: mocks.leads },
    alerts: { list: mocks.alerts },
  },
}))

import DashboardScreen from './DashboardScreen'

const renderScreen = () => render(<MemoryRouter><DashboardScreen /></MemoryRouter>)

const sparkline14 = (base) => Array.from({ length: 14 }, (_, i) => ({
  date: `2026-07-${String(i + 1).padStart(2, '0')}`, value: base + i,
}))

beforeEach(() => {
  vi.clearAllMocks()
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.alerts.mockResolvedValue({ data: { alerts: [] } })
  mocks.leads.mockResolvedValue({ data: [] })
  mocks.dashboardV2.mockResolvedValue({ data: {
    window_days: 14,
    conversations: { total: 37, sparkline: sparkline14(1) },
    mer: {
      spend: '4200.00', spend_currency: 'USD',
      signed_ca_mad: '96000.00', signed_ca_currency: 'MAD',
      mer_ratio: null, odoo_configured: true,
      spend_sparkline: sparkline14(200),
      signed_ca_sparkline: sparkline14(4000),
      note: 'Dépense en devise du compte Meta, CA signé en MAD (Odoo) — jamais convertie automatiquement.',
    },
  } })
})

describe('DashboardScreen — ADSDEEP61 Dashboard v2', () => {
  it('affiche la tuile conversations avec le total et sa sparkline', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.dashboardV2).toHaveBeenCalled())
    expect(await screen.findByTestId('ae-dv2-conversations-total')).toHaveTextContent('37')
    expect(screen.getByTestId('ae-dv2-conversations-sparkline')).toBeInTheDocument()
  })

  it('affiche la tuile MER avec les DEUX devises côte à côte, jamais fusionnées', async () => {
    renderScreen()
    const mer = await screen.findByTestId('ae-dv2-mer')
    expect(mer).toHaveTextContent('4 200 USD') // dépense Meta, devise du compte
    expect(mer).toHaveTextContent('96 000 MAD') // CA signé Odoo, toujours MAD
    // Aucun ratio inventé quand l'API n'en fournit pas (devises différentes).
    expect(screen.queryByTestId('ae-dv2-mer-ratio')).toBeNull()
    expect(screen.getByTestId('ae-dv2-mer-note')).toHaveTextContent('jamais convertie')
  })

  it('affiche le ratio MER SEULEMENT quand l\'API le fournit (même devise)', async () => {
    mocks.dashboardV2.mockResolvedValue({ data: {
      window_days: 14,
      conversations: { total: 10, sparkline: sparkline14(0) },
      mer: {
        spend: '1000.00', spend_currency: 'MAD',
        signed_ca_mad: '5000.00', signed_ca_currency: 'MAD',
        mer_ratio: '5.0000', odoo_configured: true,
        spend_sparkline: sparkline14(50), signed_ca_sparkline: sparkline14(300),
        note: 'note',
      },
    } })
    renderScreen()
    expect(await screen.findByTestId('ae-dv2-mer-ratio')).toHaveTextContent('5')
  })

  it('les sparklines des deux montants MER sont rendues', async () => {
    renderScreen()
    await screen.findByTestId('ae-dv2-mer')
    expect(screen.getByTestId('ae-dv2-mer-spend-sparkline')).toBeInTheDocument()
    expect(screen.getByTestId('ae-dv2-mer-ca-sparkline')).toBeInTheDocument()
  })
})

// Régression (couverte aussi par DashboardScreen.test.jsx /
// DashboardScreen.pacing.test.jsx, qui mockent `metrics` SANS `dashboardV2` et
// passent déjà) : le garde `adsengineApi.metrics?.dashboardV2` de l'écran ne
// doit jamais faire planter les autres suites de ce module.
