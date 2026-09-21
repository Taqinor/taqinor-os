import { describe, it, expect, vi, beforeAll } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

/* XPOS11 — smoke du tableau de bord ventes comptoir (API mockée). */

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
    getDashboard: () => Promise.resolve({
      data: {
        nb_ventes: 3,
        total_ttc: '4500',
        panier_moyen: '1500',
        taux_retour_pct: '0.00',
        par_jour: { '2026-07-06': '4500' },
        par_caissier: { reda: '4500' },
        par_mode_paiement: { especes: '4500' },
        par_categorie: { Accessoires: '4500' },
        par_produit: { 'Câble 6mm²': { total: '4500', quantite: '3' } },
      },
    }),
    exportDashboardUrl: () => '/pos/ventes/dashboard-export/',
  },
}))

vi.mock('../../api/axios', () => ({ default: { defaults: { baseURL: '' } } }))

import DashboardScreen from './DashboardScreen'

function withProviders(ui) {
  return render(
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>,
  )
}

describe('rendu smoke de DashboardScreen', () => {
  it('affiche les KPIs et une ventilation', async () => {
    withProviders(<DashboardScreen />)
    expect(screen.getByRole('heading', { name: /tableau de bord/i })).toBeInTheDocument()
    await waitFor(() => expect(screen.getByTestId('dashboard-kpis')).toBeInTheDocument())
    expect(screen.getByText('Par mode de paiement')).toBeInTheDocument()
  })
})
