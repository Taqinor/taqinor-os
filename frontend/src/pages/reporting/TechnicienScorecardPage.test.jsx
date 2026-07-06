import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
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

/* XFSM17 — scorecard technicien vs moyenne équipe
   (reporting/insights/technicien-scorecard/, ?technicien= requis). */

vi.mock('../../api/axios', () => ({
  default: {
    get: vi.fn(() => Promise.resolve({
      data: [{ id: 1, username: 'sami' }],
    })),
  },
}))

vi.mock('../../api/reportingApi', () => ({
  default: {
    technicienScorecard: vi.fn(() => Promise.resolve({
      data: {
        scorecard: {
          interventions_terminees: 12, duree_reelle_moyenne_jours: 1.5,
          taux_recidive_pct: 5, ponctualite_pct: 90, nps: 60, utilisation_pct: 75,
        },
        moyenne_equipe: {
          nb_techniciens: 4, interventions_terminees: 10,
          duree_reelle_moyenne_jours: 2, taux_recidive_pct: 8,
          ponctualite_pct: 85, nps: 50, utilisation_pct: 70,
        },
      },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import TechnicienScorecardPage from './TechnicienScorecardPage'

describe('TechnicienScorecardPage (XFSM17)', () => {
  it("affiche un état vide tant qu'aucun technicien n'est choisi", async () => {
    renderPage(<TechnicienScorecardPage />)
    expect(await screen.findByText('Choisissez un technicien')).toBeInTheDocument()
    expect(reportingApi.technicienScorecard).not.toHaveBeenCalled()
  })

  it('charge le scorecard une fois un technicien sélectionné', async () => {
    renderPage(<TechnicienScorecardPage />)

    const select = await screen.findByLabelText('Choisir un technicien')
    select.click()
    const option = await screen.findByText('sami')
    option.click()

    await waitFor(() => expect(reportingApi.technicienScorecard).toHaveBeenCalledWith({ technicien: '1' }))
    expect(await screen.findByText('12')).toBeInTheDocument()
  })
})
