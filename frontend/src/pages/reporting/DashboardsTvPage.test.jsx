import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* XPLT10 — kiosque TV plein écran (`/dashboards-tv`, core/dashboards-tv/). */

// recharts (ResponsiveContainer) mesure sa taille — jsdom n'a pas ResizeObserver.
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/coreApi', () => ({
  default: {
    dashboardsTv: {
      list: vi.fn(() => Promise.resolve({
        data: { dashboards: [{ id: 1, titre: 'Dashboard société', layout: { widgets: [] } }] },
      })),
    },
  },
}))

import coreApi from '../../api/coreApi'
import DashboardsTvPage from './DashboardsTvPage'

describe('DashboardsTvPage (XPLT10 — kiosque TV)', () => {
  it('affiche le premier dashboard partagé', async () => {
    render(<DashboardsTvPage />)

    expect(await screen.findByTestId('dashboards-tv')).toBeInTheDocument()
    expect(screen.getByText('Dashboard société')).toBeInTheDocument()
    await waitFor(() => expect(coreApi.dashboardsTv.list).toHaveBeenCalled())
  })

  it('affiche un état vide si aucun dashboard partagé', async () => {
    coreApi.dashboardsTv.list.mockResolvedValueOnce({ data: { dashboards: [] } })
    render(<DashboardsTvPage />)

    expect(await screen.findByText(/Aucun dashboard partagé/i)).toBeInTheDocument()
  })

  it('affiche un état vide (pas de <pre>) quand le dashboard n’a aucun widget', async () => {
    render(<DashboardsTvPage />)

    expect(await screen.findByText('Aucun widget configuré')).toBeInTheDocument()
    expect(document.querySelector('pre')).toBeNull()
  })

  it('VX118(c) — un layout stats/charts se rend avec le kit existant, jamais du JSON brut', async () => {
    coreApi.dashboardsTv.list.mockResolvedValueOnce({
      data: {
        dashboards: [{
          id: 2,
          titre: 'Production solaire',
          layout: {
            widgets: [
              { id: 'w1', titre: 'kWc installés', valeur: '482' },
              { id: 'w2', titre: 'Production 7 j', serie: [12, 18, 15, 22, 19, 25, 30] },
              { id: 'w3', titre: 'Alertes' },
            ],
          },
        }],
      },
    })
    render(<DashboardsTvPage />)

    expect(await screen.findByText('Production solaire')).toBeInTheDocument()
    // Grand chiffre lisible à 3 mètres pour le widget scalaire.
    expect(screen.getByText('482')).toHaveClass('text-6xl')
    // Le widget série rend un graphique (svg recharts), pas un JSON.
    expect(screen.getByText('Production 7 j')).toBeInTheDocument()
    // Le widget sans donnée exploitable retombe sur ChartEmpty, jamais un <pre>.
    expect(screen.getByText('Alertes')).toBeInTheDocument()
    expect(screen.getByText('Aucune donnée exploitable pour ce widget.')).toBeInTheDocument()
    expect(document.querySelector('pre')).toBeNull()
    expect(screen.queryByText(/"widgets"/)).not.toBeInTheDocument()
  })
})
