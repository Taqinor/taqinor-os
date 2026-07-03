import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
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

/* WR8 — La page cohortes rend le taux de signature + délai moyen par cohorte
   depuis GET /reporting/insights/cohorts/. */

vi.mock('../../api/reportingApi', () => ({
  default: {
    cohorts: vi.fn(() => Promise.resolve({
      data: {
        from: '2025-07-01', to: '2026-06-30', group_by: null,
        cohorts: [
          { cohorte: '2026-04', nb_leads: 20, nb_signes: 6, taux_signature: 30.0, avg_days_to_sign: 18.5 },
          { cohorte: '2026-05', nb_leads: 15, nb_signes: 9, taux_signature: 60.0, avg_days_to_sign: 12.0 },
        ],
      },
    })),
  },
}))

import reportingApi from '../../api/reportingApi'
import CohortsPage from './CohortsPage'

describe('CohortsPage (WR8 — cohortes de leads)', () => {
  it('rend les cohortes (taux + délai) dans le tableau', async () => {
    renderPage(<CohortsPage />)

    // Les mois de cohorte apparaissent (tableau + libellés du graphique).
    expect((await screen.findAllByText('2026-04')).length).toBeGreaterThan(0)
    expect(screen.getAllByText('2026-05').length).toBeGreaterThan(0)
    // En-têtes du tableau (DataTable rend l'en-tête en double : mesure + réel).
    expect(screen.getAllByText('Taux signature').length).toBeGreaterThan(0)
    expect(screen.getAllByText('Délai moyen').length).toBeGreaterThan(0)

    expect(reportingApi.cohorts).toHaveBeenCalledWith({})
  })
})
