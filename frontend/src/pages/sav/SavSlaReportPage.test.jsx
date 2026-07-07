import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* XSAV8 — rapport de conformité SLA + KPI avancés SAV. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: { getSavSlaReport: vi.fn() },
}))

import savApi from '../../api/savApi'
import SavSlaReportPage from './SavSlaReportPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SavSlaReportPage', () => {
  it('affiche les KPI agrégés et le tableau par priorité', async () => {
    savApi.getSavSlaReport.mockResolvedValue({
      data: {
        total_tickets: 12,
        par_priorite: [
          { priorite: 'haute', label: 'Haute', total: 5, pct_premiere_reponse_ok: 80, pct_resolution_ok: 60 },
        ],
        par_technicien: [
          { technicien_id: 1, technicien: 'Yassine', total: 5, pct_premiere_reponse_ok: 100, pct_resolution_ok: 80, reouvertures: 1 },
        ],
        delai_moyen_premiere_reponse_jours: 1.2,
        delai_moyen_resolution_jours: 3.4,
        backlog_vieilli: { buckets: { '0_2j': 2, '3_7j': 1, plus_7j: 0 }, ids: {} },
        preventif_vs_correctif: { nb_preventif: 4, nb_correctif: 8, pct_preventif: 33.3 },
        visites_preventives: { total_evaluees: 4, a_heure: 3, en_retard: 1, pct_a_heure: 75 },
        reouverture: null,
      },
    })
    render(<SavSlaReportPage />)
    expect(await screen.findByText('12 tickets évalués')).toBeInTheDocument()
    expect(screen.getByText('Haute')).toBeInTheDocument()
    expect(screen.getByText('Yassine')).toBeInTheDocument()
  })

  it('affiche un état d\'erreur avec bouton Réessayer si le chargement échoue', async () => {
    savApi.getSavSlaReport.mockRejectedValue(new Error('fail'))
    render(<SavSlaReportPage />)
    expect(await screen.findByText('Chargement impossible')).toBeInTheDocument()
  })
})
