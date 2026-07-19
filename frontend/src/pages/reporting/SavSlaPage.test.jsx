import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* XSAV8 — conformité SLA + KPI SAV avancés (reporting/insights/sav-sla/). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    savSlaInsight: vi.fn(() => Promise.resolve({
      data: {
        total_tickets: 42,
        par_priorite: [{ priorite: 'haute', label: 'Haute', total: 10, pct_premiere_reponse_ok: 90, pct_resolution_ok: 80 }],
        par_technicien: [{ technicien_id: 1, technicien: 'sami', total: 5, pct_premiere_reponse_ok: 100, pct_resolution_ok: 100, reouvertures: 0 }],
        delai_moyen_premiere_reponse_jours: 1.2,
        delai_moyen_resolution_jours: 3.5,
        backlog_vieilli: { buckets: { '0_2j': 2, '3_7j': 1, plus_7j: 0 }, ids: {} },
        preventif_vs_correctif: { nb_preventif: 5, nb_correctif: 10, pct_preventif: 33.3 },
        visites_preventives: { total_evaluees: 5, a_heure: 4, en_retard: 1, pct_a_heure: 80 },
        reouverture: { total_reouvertures: 2, taux_pour_100_tickets: 4.8 },
      },
    })),
    // WIR102 — analytique SAV additionnelle (pivot / coût moyen / taux d'attache).
    savTauxAttache: vi.fn(() => Promise.resolve({
      data: { total: 8, avec_contrat: 6, taux_pct: 75.0 },
    })),
    savTicketsPivot: vi.fn(() => Promise.resolve({
      data: {
        row_keys: [['karim']],
        col_keys: [['ouvert'], ['clos']],
        cells: { karim: { ouvert: 2, clos: 3 } },
        row_totals: { karim: 5 },
      },
    })),
    savTicketsCoutMoyen: vi.fn(() => Promise.resolve({
      data: { rows: [{ technicien_responsable__username: 'nadia', cout_moyen: 120.5, n: 5 }] },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import SavSlaPage from './SavSlaPage'

describe('SavSlaPage (XSAV8)', () => {
  it('affiche les KPIs et les tableaux par priorité/technicien', async () => {
    render(<SavSlaPage />)

    expect(await screen.findByText('42')).toBeInTheDocument()
    expect(screen.getByText('Haute')).toBeInTheDocument()
    expect(screen.getByText('sami')).toBeInTheDocument()
    await waitFor(() => expect(reportingApi.savSlaInsight).toHaveBeenCalled())
  })

  it('WIR102 — affiche taux d’attache, pivot tickets et coût moyen', async () => {
    render(<SavSlaPage />)

    expect(await screen.findByText('Taux d’attache contrat')).toBeInTheDocument()
    expect(await screen.findByText('Tickets par technicien et statut')).toBeInTheDocument()
    expect(await screen.findByText('Coût interne moyen par technicien')).toBeInTheDocument()
    await waitFor(() => expect(reportingApi.savTauxAttache).toHaveBeenCalled())
  })
})
