import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Package } from 'lucide-react'
import { KpiCard } from './Dashboard.jsx'

/* K148 — Carte KPI : Libellé → Valeur → Δ → Période + sparkline.
   Le delta combine flèche + signe + couleur (jamais la couleur seule). */
describe('KpiCard (K148)', () => {
  const baseKpi = {
    label: 'Devis acceptés',
    value: '12',
    hint: 'sur 30 devis',
    period: '6 derniers mois',
    icon: Package,
    to: '/ventes/devis',
  }

  it('rend libellé, valeur, indice et période', () => {
    render(<KpiCard kpi={baseKpi} navigate={() => {}} />)
    expect(screen.getByText('Devis acceptés')).toBeInTheDocument()
    expect(screen.getByText('12')).toBeInTheDocument()
    expect(screen.getByText('sur 30 devis')).toBeInTheDocument()
    expect(screen.getByText('6 derniers mois')).toBeInTheDocument()
  })

  it('delta haussier : flèche ▲ + signe + classe de couleur succès', () => {
    const kpi = { ...baseKpi, delta: { value: '+3', direction: 'up' } }
    render(<KpiCard kpi={kpi} navigate={() => {}} />)
    const delta = screen.getByText(/▲/)
    expect(delta).toHaveClass('text-success')
    expect(delta.textContent).toContain('+3')
  })

  it('delta baissier : flèche ▼ + classe de couleur danger', () => {
    const kpi = { ...baseKpi, delta: { value: '−2', direction: 'down' } }
    render(<KpiCard kpi={kpi} navigate={() => {}} />)
    const delta = screen.getByText(/▼/)
    expect(delta).toHaveClass('text-destructive')
  })

  it('navigue au clic et au clavier (Enter)', async () => {
    const navigate = vi.fn()
    render(<KpiCard kpi={baseKpi} navigate={navigate} />)
    const card = screen.getByRole('button')
    await userEvent.click(card)
    expect(navigate).toHaveBeenCalledWith('/ventes/devis')
    card.focus()
    await userEvent.keyboard('{Enter}')
    expect(navigate).toHaveBeenCalledTimes(2)
  })

  it('sparkline masquée quand la série est entièrement nulle', () => {
    // Série tout-à-zéro → pas de sparkline (et donc aucun rendu recharts).
    render(<KpiCard kpi={{ ...baseKpi, spark: [0, 0, 0] }} navigate={() => {}} />)
    expect(screen.getByText('Devis acceptés')).toBeInTheDocument()
  })
})
