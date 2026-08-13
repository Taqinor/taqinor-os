import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import rhApi from '../../api/rhApi'
import RhCockpit from './RhCockpit.jsx'

/* XRH31 — le cockpit RH expose le top des employés par risque d'attrition
   (`/rh/cockpit/top-risque-attrition/`). Les bandes viennent du scorer serveur
   `core/attrition_risk.py` : `faible` / `moyen` / `élevé` (accentué). */

vi.mock('../../api/rhApi', () => ({
  default: {
    getCockpit: vi.fn(() => Promise.resolve({ data: { effectif_total: 12, alertes: {}, turnover: {} } })),
    getEcheances: vi.fn(() => Promise.resolve({ data: [] })),
    getTableauBordHse: vi.fn(() => Promise.resolve({ data: {} })),
    getTopRisqueAttrition: vi.fn(() => Promise.resolve({ data: [] })),
    // ZRH11 — rapport de rétention/turnover annuel.
    getRapportTurnover: vi.fn(() => Promise.resolve({ data: null })),
  },
}))

function renderCockpit() {
  return render(
    <MemoryRouter>
      <ThemeProvider>
        <RhCockpit />
      </ThemeProvider>
    </MemoryRouter>,
  )
}

describe('RhCockpit — risque d’attrition (XRH31)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche le top des employés à risque avec leur bande serveur', async () => {
    rhApi.getCockpit.mockResolvedValueOnce({
      data: { effectif_total: 12, alertes: {}, turnover: {} },
    })
    rhApi.getEcheances.mockResolvedValueOnce({ data: [] })
    rhApi.getTableauBordHse.mockResolvedValueOnce({ data: {} })
    rhApi.getTopRisqueAttrition.mockResolvedValueOnce({
      data: [{ employe_id: 9, employe_nom: 'Bennani Youssef', score: 72, band: 'élevé' }],
    })
    renderCockpit()

    expect(await screen.findByText('Risque d’attrition — top 5')).toBeInTheDocument()
    expect(screen.getByText('Bennani Youssef')).toBeInTheDocument()
    expect(screen.getByText('Élevé')).toBeInTheDocument()
    expect(rhApi.getTopRisqueAttrition).toHaveBeenCalledWith({ limite: 5 })
  })

  it('reste utilisable quand le score d’attrition échoue', async () => {
    rhApi.getTopRisqueAttrition.mockRejectedValueOnce(new Error('403'))
    renderCockpit()

    expect((await screen.findAllByText('Cockpit RH')).length).toBeGreaterThan(0)
    expect(screen.queryByText('Risque d’attrition — top 5')).toBeNull()
  })
})

describe('RhCockpit — rétention & turnover annuel (ZRH11)', () => {
  beforeEach(() => vi.clearAllMocks())

  it('affiche le rapport annuel avec les clés du sélecteur serveur', async () => {
    rhApi.getRapportTurnover.mockResolvedValueOnce({
      data: {
        annee: 2026, effectif_debut: 10, effectif_fin: 12,
        par_mois: [], entrees_total: 4, sorties_total: 2,
        taux_turnover_pct: 18.2, anciennete_moyenne_ans: 3.4,
        retention_12m_pct: 75.0,
      },
    })
    renderCockpit()

    expect(await screen.findByText('Rétention & turnover 2026')).toBeInTheDocument()
    expect(screen.getByText('18,2 %')).toBeInTheDocument()
    expect(screen.getByText('4 / 2')).toBeInTheDocument()
  })
})
