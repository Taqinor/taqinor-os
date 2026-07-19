import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'

/* XSAV8 — rapport de conformité SLA + KPI avancés SAV. savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    getSavSlaReport: vi.fn(),
    // WIR121 — 4 analyses fleet-wide surfacées dans le rapport SLA.
    getSavPareto: vi.fn(() => Promise.resolve({ data: { results: [] } })),
    getSavFiabiliteParc: vi.fn(() => Promise.resolve({ data: { results: [], couts_inclus: false } })),
    getSavPartsForecast: vi.fn(() => Promise.resolve({ data: [] })),
    getSavResumeParEquipe: vi.fn(() => Promise.resolve({ data: { results: [] } })),
  },
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

  it('WIR121 — surface les 4 analyses fleet-wide avec données réelles', async () => {
    savApi.getSavSlaReport.mockResolvedValue({ data: { total_tickets: 0 } })
    savApi.getSavPareto.mockResolvedValue({
      data: { results: [{ cle: 1, libelle: 'Onduleur 5kW', nb_tickets: 9, pct: 45, pct_cumule: 45 }] },
    })
    savApi.getSavFiabiliteParc.mockResolvedValue({
      data: { results: [{ equipement_id: 2, numero_serie: 'SN-2', produit_nom: 'Pompe', nb_tickets_correctifs: 3, mtbf_jours: 40, mttr_jours: 2 }], couts_inclus: false },
    })
    savApi.getSavPartsForecast.mockResolvedValue({
      data: [{ produit: 7, nom: 'Fusible', sku: 'F16', total_consomme: 12, consommation_mensuelle_moy: 1, qte_suggere_reappro: 2 }],
    })
    savApi.getSavResumeParEquipe.mockResolvedValue({
      data: { results: [{ equipe_id: 5, equipe_nom: 'Équipe Nord', ouverts: 4, en_retard_sla: 1, preventifs_dus: 2, correctifs_urgents: 1 }] },
    })
    render(<SavSlaReportPage />)

    expect(await screen.findByText('Pareto des pannes (par produit)')).toBeInTheDocument()
    expect(await screen.findByText('Onduleur 5kW')).toBeInTheDocument()
    expect(screen.getByText('Fusible (F16)')).toBeInTheDocument()
    expect(screen.getByText('Équipe Nord')).toBeInTheDocument()
    expect(screen.getByText('Fiabilité du parc (MTBF / MTTR)')).toBeInTheDocument()
  })
})
