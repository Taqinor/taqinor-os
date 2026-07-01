import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import {
  transitionsPour, estTerminal, STATUT_MAP, GRAVITE_MAP,
} from './litigesStatus'
import FilterSelect from './FilterSelect'

function wrap(ui) {
  return (
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

describe('litiges state machine helpers', () => {
  it('transitionsPour reflète la machine à états backend', () => {
    expect(transitionsPour('ouverte')).toEqual(['prendre_en_charge', 'rejeter'])
    expect(transitionsPour('en_traitement')).toEqual(['resoudre', 'rejeter'])
    expect(transitionsPour('resolue')).toEqual([])
    expect(transitionsPour('rejetee')).toEqual([])
  })

  it('estTerminal marque resolue/rejetee comme terminaux', () => {
    expect(estTerminal('resolue')).toBe(true)
    expect(estTerminal('rejetee')).toBe(true)
    expect(estTerminal('ouverte')).toBe(false)
    expect(estTerminal('en_traitement')).toBe(false)
  })

  it('les cartes de statut/gravité couvrent toutes les valeurs backend', () => {
    expect(Object.keys(STATUT_MAP).sort()).toEqual(
      ['en_traitement', 'ouverte', 'rejetee', 'resolue'],
    )
    expect(Object.keys(GRAVITE_MAP).sort()).toEqual(
      ['elevee', 'faible', 'moyenne'],
    )
  })
})

describe('FilterSelect (smoke)', () => {
  it('rend les options de gravité et la valeur courante', () => {
    render(wrap(
      <FilterSelect
        value="elevee"
        onChange={() => {}}
        options={Object.entries(GRAVITE_MAP).map(([value, v]) => ({ value, label: v.label }))}
        aria-label="Gravité"
      />,
    ))
    const select = screen.getByRole('combobox', { name: 'Gravité' })
    expect(select.value).toBe('elevee')
    expect(screen.getByText('Élevée')).toBeTruthy()
  })
})
