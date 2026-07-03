import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'

/* WR9 — panneau consultatif du pipeline : atteinte des objectifs (FG39),
   ROI par source (FG34), retards SLA de premier contact (FG28). crmApi mocké. */

vi.mock('../../../api/crmApi', () => ({
  default: {
    getObjectifsAttainment: vi.fn(() => Promise.resolve({
      data: [{
        id: 1, metric: 'signed_count', metric_display: 'Leads signés',
        period_type: 'month', period_year: 2026, period_month: 6,
        period_quarter: null, cible: '10.00', owner: 3, owner_nom: 'sami',
        realise: '7.00', taux: 70.0,
        period_start: '2026-06-01', period_end: '2026-06-30',
      }],
    })),
    getRoiSources: vi.fn(() => Promise.resolve({
      data: [{
        canal: 'site_web', utm_campaign: 'ete-2026', lead_count: 12,
        signed_count: 3, win_rate: 25.0, signed_value_ttc: 91000,
      }],
    })),
    getSlaBreach: vi.fn(() => Promise.resolve({
      data: {
        sla_hours: 24,
        count: 2,
        results: [
          { id: 5, nom: 'Alami', date_creation: '2026-06-25T10:00:00Z' },
          { id: 6, nom: 'Bennani', date_creation: '2026-06-26T10:00:00Z' },
        ],
      },
    })),
  },
}))

import crmApi from '../../../api/crmApi'
import CrmInsightsPanel from './CrmInsightsPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('CrmInsightsPanel (WR9 — FG39/FG34/FG28)', () => {
  it('rend les trois surfaces avec les données serveur', async () => {
    render(<CrmInsightsPanel />)
    expect(screen.getByTestId('crm-insights')).toBeInTheDocument()

    // FG39 — objectif avec taux et période.
    await waitFor(() => expect(screen.getByText('Leads signés — sami')).toBeInTheDocument())
    expect(screen.getByText('70 %')).toBeInTheDocument()

    // FG34 — ligne ROI (canal + campagne + valeur signée).
    expect(screen.getByText('site_web')).toBeInTheDocument()
    expect(screen.getByText('· ete-2026')).toBeInTheDocument()
    expect(screen.getByText('3 (25 %)')).toBeInTheDocument()

    // FG28 — retards SLA : compte + description avec le délai société.
    expect(screen.getByText(/plus de 24 h/)).toBeInTheDocument()
    expect(screen.getByText('Alami')).toBeInTheDocument()
    expect(screen.getByText('Bennani')).toBeInTheDocument()

    expect(crmApi.getObjectifsAttainment).toHaveBeenCalled()
    expect(crmApi.getRoiSources).toHaveBeenCalled()
    expect(crmApi.getSlaBreach).toHaveBeenCalled()
  })

  it('reste lisible quand les endpoints échouent', async () => {
    crmApi.getObjectifsAttainment.mockRejectedValueOnce(new Error('x'))
    crmApi.getRoiSources.mockRejectedValueOnce(new Error('x'))
    crmApi.getSlaBreach.mockRejectedValueOnce(new Error('x'))
    render(<CrmInsightsPanel />)
    await waitFor(() =>
      expect(screen.getAllByText('Données indisponibles — réessayez.').length)
        .toBeGreaterThanOrEqual(2))
  })
})
