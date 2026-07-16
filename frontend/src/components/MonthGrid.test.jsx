import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent } from '@testing-library/react'
import MonthGrid from './MonthGrid'

/* VX25 — MonthGrid : grille mensuelle partagée (cellules lundi-dimanche,
   navigation mois, « Aujourd'hui »), paramétrée par renderCell. */

afterEach(() => { cleanup() })

const renderCell = (cell) => (
  <div key={cell.key} data-testid={`cell-${cell.key}`} className="cal-cell">
    {cell.dayNumber}
  </div>
)

describe('MonthGrid (VX25)', () => {
  it('affiche les 7 jours de la semaine en français (lundi en premier)', () => {
    render(<MonthGrid initialMonth={new Date(2026, 5, 1)} renderCell={renderCell} />)
    expect(screen.getByText('Lun')).toBeInTheDocument()
    expect(screen.getByText('Dim')).toBeInTheDocument()
  })

  it('affiche le titre du mois courant (fr-FR, majuscule initiale)', () => {
    render(<MonthGrid initialMonth={new Date(2026, 5, 1)} renderCell={renderCell} />)
    expect(screen.getByText('Juin 2026')).toBeInTheDocument()
  })

  it('la navigation « suivant » avance d\'un mois et notifie onMonthChange', () => {
    const onMonthChange = vi.fn()
    render(
      <MonthGrid
        initialMonth={new Date(2026, 5, 1)}
        renderCell={renderCell}
        onMonthChange={onMonthChange}
      />,
    )
    fireEvent.click(screen.getByLabelText('Mois suivant'))
    expect(screen.getByText('Juillet 2026')).toBeInTheDocument()
    expect(onMonthChange).toHaveBeenCalledWith(new Date(2026, 6, 1))
  })

  it('« Aujourd\'hui » ramène au mois courant', () => {
    render(<MonthGrid initialMonth={new Date(2020, 0, 1)} renderCell={renderCell} />)
    fireEvent.click(screen.getByText("Aujourd'hui"))
    const now = new Date()
    const expectedTitle = now.toLocaleDateString('fr-FR', { month: 'long', year: 'numeric' })
    const capitalized = expectedTitle.charAt(0).toUpperCase() + expectedTitle.slice(1)
    expect(screen.getByText(capitalized)).toBeInTheDocument()
  })

  it('rend headerExtra dans la zone d\'outils', () => {
    render(
      <MonthGrid
        initialMonth={new Date(2026, 5, 1)}
        renderCell={renderCell}
        headerExtra={<span data-testid="extra-tool">Outil</span>}
      />,
    )
    expect(screen.getByTestId('extra-tool')).toBeInTheDocument()
  })

  it('délègue chaque cellule à renderCell', () => {
    render(<MonthGrid initialMonth={new Date(2026, 5, 1)} renderCell={renderCell} />)
    // Juin 2026 commence un lundi — la cellule du 1er juin doit exister.
    expect(screen.getByTestId('cell-2026-06-01')).toBeInTheDocument()
  })
})
