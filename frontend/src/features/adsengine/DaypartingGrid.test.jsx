import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent } from '@testing-library/react'

/* ADSDEEP36 — grille heure×jour du dayparting (RTL/French) : 7 jours x 24
   heures, toggle par case, contrôlée (value/onChange), lecture seule possible. */

import DaypartingGrid from './DaypartingGrid'
import { emptyGrid, DP_DAYS } from './adsengine'

describe('DaypartingGrid (ADSDEEP36)', () => {
  it('emptyGrid produit 7 jours de 24 heures, toutes autorisées par défaut', () => {
    const grid = emptyGrid()
    expect(Object.keys(grid).sort()).toEqual([...DP_DAYS].sort())
    DP_DAYS.forEach(day => {
      expect(grid[day]).toHaveLength(24)
      expect(grid[day].every(v => v === 1)).toBe(true)
    })
  })

  it('rend 7 jours × 24 heures de cases cliquables', () => {
    render(<DaypartingGrid value={emptyGrid()} onChange={() => {}} />)
    DP_DAYS.forEach(day => {
      for (let h = 0; h < 24; h++) {
        expect(screen.getByTestId(`dp-cell-${day}-${h}`)).toBeInTheDocument()
      }
    })
  })

  it('cliquer une case bloquée l\'autorise (toggle) et appelle onChange', () => {
    const grid = emptyGrid(false) // tout bloqué
    const onChange = vi.fn()
    render(<DaypartingGrid value={grid} onChange={onChange} />)
    const cell = screen.getByTestId('dp-cell-mon-9')
    expect(cell).toHaveAttribute('aria-pressed', 'false')
    fireEvent.click(cell)
    expect(onChange).toHaveBeenCalledTimes(1)
    const [next] = onChange.mock.calls[0]
    expect(next.mon[9]).toBe(1)
    // Les autres heures du lundi restent inchangées (immutabilité de la mise à jour).
    expect(next.mon[8]).toBe(0)
    // La grille d'origine n'est PAS mutée.
    expect(grid.mon[9]).toBe(0)
  })

  it('readOnly désactive les cases (aucun clic ne déclenche onChange)', () => {
    const onChange = vi.fn()
    render(<DaypartingGrid value={emptyGrid()} onChange={onChange} readOnly />)
    const cell = screen.getByTestId('dp-cell-tue-3')
    expect(cell).toBeDisabled()
    fireEvent.click(cell)
    expect(onChange).not.toHaveBeenCalled()
  })
})
