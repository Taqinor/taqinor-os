import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* VX29 — CommercialDashboard restylé sur le kit (Card/Stat/Table/BarArrondie).
   Couvre : rendu des KPIs et, surtout, la correction du bug EmptyState — la
   version d'avant passait `message=` (ignoré par l'API réelle title/description),
   donc le texte ne s'affichait pas. Ici on prouve que title + description
   s'affichent, et que l'export est désactivé sans données. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    commercialDashboard: vi.fn(() => Promise.resolve({
      data: {
        total_leads: 0,
        total_signes: 0,
        win_rate_pct: 0,
        sales_velocity: { avg_days: null, sample_count: 0 },
        funnel: [],
        time_in_stage: [],
        leaderboard: [],
      },
    })),
    winLossBySource: vi.fn(() => Promise.resolve({
      data: {
        summary: { nb_total: 0, nb_won: 0, nb_lost: 0, overall_close_rate_pct: 0 },
        by_canal: [],
        top_loss_reasons: [],
        by_source_technique: [],
      },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import CommercialDashboard from './CommercialDashboard'

describe('CommercialDashboard (VX29)', () => {
  it('affiche le titre et les libellés de KPI', async () => {
    render(<CommercialDashboard />)
    expect(await screen.findByText('Tableau commercial')).toBeInTheDocument()
    expect(await screen.findByText('Total leads')).toBeInTheDocument()
    await waitFor(() => expect(reportingApi.commercialDashboard).toHaveBeenCalled())
  })

  it('VX148 — entonnoir vide rend ChartEmpty (pas un EmptyState nu)', async () => {
    render(<CommercialDashboard />)
    expect(await screen.findByText("Aucune donnée d'entonnoir")).toBeInTheDocument()
    expect(screen.getByText("Aucun lead n'a encore progressé dans le pipeline sur cette période.")).toBeInTheDocument()
  })

  it('rend un EmptyState avec title + description quand le classement est vide (bug corrigé)', async () => {
    render(<CommercialDashboard />)
    fireEvent.click(await screen.findByText('Classement'))
    expect(await screen.findByText('Aucun devis signé')).toBeInTheDocument()
    expect(screen.getByText('Aucun devis signé sur cette période.')).toBeInTheDocument()
  })

  it('désactive le bouton Exporter quand le classement est vide', async () => {
    render(<CommercialDashboard />)
    fireEvent.click(await screen.findByText('Classement'))
    const btn = await screen.findByRole('button', { name: /Exporter/i })
    expect(btn).toBeDisabled()
  })
})
