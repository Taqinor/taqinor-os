import { describe, it, expect, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { declarerResizeObserver, renderPage } from './pageThemee.testHelpers.jsx'

declarerResizeObserver()

/* NTOBS16 — destination du lien « Voir le rapport SLA complet ». */

vi.mock('../../api/parametresApi', () => ({
  default: { getSlaSnapshots: vi.fn() },
}))

import parametresApi from '../../api/parametresApi'
import SlaReportPage from './SlaReportPage'

describe('SlaReportPage (NTOBS16)', () => {
  it('liste les snapshots avec leur disponibilité', async () => {
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({
      data: [{ id: 1, periode: '2026-06-01', uptime_pct: '99.9500' }],
    })
    renderPage(<SlaReportPage />)
    await waitFor(() => expect(screen.getByText(/99.95% disponible/)).toBeInTheDocument())
  })

  it("affiche un etat vide propre sans snapshot", async () => {
    parametresApi.getSlaSnapshots.mockResolvedValueOnce({ data: [] })
    renderPage(<SlaReportPage />)
    await waitFor(() =>
      expect(screen.getByText(/Aucun rapport SLA/)).toBeInTheDocument())
  })
})
