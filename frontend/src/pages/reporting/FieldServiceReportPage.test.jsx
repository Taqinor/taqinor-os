import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* XFSM16 — analytics field service consolidés (reporting/reports/field/). */

vi.mock('../../api/reportingApi', () => ({
  default: {
    fieldServiceReport: vi.fn(() => Promise.resolve({
      data: {
        total_interventions: 30,
        par_type: [], par_statut: [],
        total_tickets: 20,
        first_time_fix: { nb_resolus: 18, nb_ftf: 15, pct_ftf: 83.3 },
        mttr_jours_moyen: 2.1,
        ponctualite: { nb_mesurees: 10, nb_a_lheure: 9, taux_pct: 90 },
        recidive: { total: 1, taux_pct: 5 },
        temps_trajet_vs_site: { trajet_moyen_min: 25, duree_sur_site_moyenne_min: 90 },
        par_technicien: [{ technicien_id: 1, technicien: 'sami', total_tickets: 5, pct_ftf: 100, mttr_jours: 1, taux_recidive_pct: 0, trajet_moyen_min: 20, duree_sur_site_moyenne_min: 80 }],
      },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import FieldServiceReportPage from './FieldServiceReportPage'

describe('FieldServiceReportPage (XFSM16)', () => {
  it('affiche les KPIs et le tableau par technicien', async () => {
    render(<FieldServiceReportPage />)

    expect(await screen.findByText('30')).toBeInTheDocument()
    expect(screen.getByText('sami')).toBeInTheDocument()
    await waitFor(() => expect(reportingApi.fieldServiceReport).toHaveBeenCalled())
  })
})
