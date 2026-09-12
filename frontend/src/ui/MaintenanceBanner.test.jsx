import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* NTOBS9/NTOBS32 — bannière in-app des fenêtres de maintenance : distingue
   visuellement « planifiée à venir » (ambre) de « en cours » (rouge). */

vi.mock('../api/coreApi', () => ({
  default: {
    maintenanceWindows: { actives: vi.fn() },
  },
}))

import coreApi from '../api/coreApi'
import MaintenanceBanner from './MaintenanceBanner'

describe('MaintenanceBanner (NTOBS9)', () => {
  it('ne rend rien sans fenêtre active', async () => {
    coreApi.maintenanceWindows.actives.mockResolvedValueOnce({ data: [] })
    const { container } = render(<MaintenanceBanner />)
    await waitFor(() => expect(coreApi.maintenanceWindows.actives).toHaveBeenCalled())
    expect(container).toBeEmptyDOMElement()
  })

  it('affiche une fenêtre planifiée à venir avec un décompte', async () => {
    const dans2h = new Date(Date.now() + 2 * 60 * 60 * 1000).toISOString()
    coreApi.maintenanceWindows.actives.mockResolvedValueOnce({
      data: [{ statut: 'planifie', debute_le: dans2h, impact: 'degrade', description: 'Bascule infra.' }],
    })
    render(<MaintenanceBanner />)
    await waitFor(() => expect(screen.getByTestId('maintenance-banner')).toBeInTheDocument())
    expect(screen.getByText(/planifiée/)).toBeInTheDocument()
  })

  it('affiche un état "en cours" distinct visuellement', async () => {
    coreApi.maintenanceWindows.actives.mockResolvedValueOnce({
      data: [{ statut: 'en_cours', debute_le: new Date().toISOString(), description: 'Dégradation en cours.' }],
    })
    render(<MaintenanceBanner />)
    const banniere = await screen.findByTestId('maintenance-banner')
    expect(banniere.className).toMatch(/red-/)
    expect(screen.getByText(/en cours/)).toBeInTheDocument()
  })
})
