import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* NTRET16 — smoke du tableau de bord retail (API mockée). */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

vi.mock('../../api/posApi', () => ({
  default: {
    getDashboardRetail: () => Promise.resolve({
      data: {
        nb_ventes: 2,
        total_ttc: '1500',
        panier_moyen: '750',
        taux_transformation_pct: '100.00',
        ventes_par_m2: '15.00',
        top_produits: [{ nom: 'Onduleur 3kW', total: '1500.00' }],
        top_categories: [{ nom: 'Onduleurs', total: '1500.00' }],
        top_vendeurs: [{ nom: 'caissier1', total: '1500.00' }],
        comparatif_boutiques: { 'Caisse Casablanca': '1000.00', 'Caisse Rabat': '500.00' },
      },
    }),
    exportDashboardRetailUrl: () => '/pos/ventes/dashboard-retail-export/',
  },
}))

vi.mock('../../api/axios', () => ({ default: { defaults: { baseURL: '' } } }))

import DashboardRetail from './DashboardRetail'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de DashboardRetail', () => {
  it('affiche les KPIs et le comparatif boutiques', async () => {
    withProviders(<DashboardRetail />)
    expect(screen.getByRole('heading', { name: /tableau de bord retail/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('dashboard-retail-kpis')).toBeInTheDocument())
    expect(screen.getByText('100.00 %')).toBeInTheDocument()
    expect(screen.getByText('Comparatif boutiques')).toBeInTheDocument()
    expect(screen.getByText('Caisse Casablanca')).toBeInTheDocument()
    expect(screen.getByText('Top produits')).toBeInTheDocument()
  })
})
