import { describe, it, expect, beforeAll } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { STATUT_MAP } from './innovationStatus'
import FilterSelect from './FilterSelect'

function wrap(ui, { route = '/' } = {}) {
  return (
    <MemoryRouter initialEntries={[route]}>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

// jsdom n'implémente pas ResizeObserver (Radix Switch/Select).
beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
})

describe('innovationStatus (NTIDE1/NTIDE4 — miroir apps.innovation.models.Idee.Statut)', () => {
  it('STATUT_MAP couvre les 5 statuts backend', () => {
    expect(Object.keys(STATUT_MAP).sort()).toEqual(
      ['examinee', 'fermee', 'ouvert', 'realisee', 'retenue'],
    )
  })
})

describe('FilterSelect (smoke)', () => {
  it('rend les options de statut et la valeur courante', () => {
    render(wrap(
      <FilterSelect
        value="retenue"
        onChange={() => {}}
        options={Object.entries(STATUT_MAP).map(([value, v]) => ({ value, label: v.label }))}
        aria-label="Statut"
      />,
    ))
    const select = screen.getByRole('combobox', { name: 'Statut' })
    expect(select.value).toBe('retenue')
    expect(screen.getByText('Retenue')).toBeTruthy()
  })
})
