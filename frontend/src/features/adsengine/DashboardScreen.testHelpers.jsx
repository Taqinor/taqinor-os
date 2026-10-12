/* Harnais partagé des tests DashboardScreen.* (ENF19) : rendu + réponses de base. */
import { render } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { createElement } from 'react'

export function renderDashboard(Screen) {
  return render(<MemoryRouter>{createElement(Screen)}</MemoryRouter>)
}

/** Réponses par défaut du dashboard : métriques de base, aucune alerte, aucun lead. */
export function seedDashboardBase(mocks) {
  mocks.dashboard.mockResolvedValue({ data: {
    cost_per_signature: 1850, spend: 4200, cpl: 95, frequency: 1.8 } })
  mocks.alerts.mockResolvedValue({ data: { alerts: [] } })
  mocks.leads.mockResolvedValue({ data: [] })
}
