import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'
import { splitTags, labelStatutArticle, KB_STATUT_MAP } from './kbStatus'
import FilterSelect from './FilterSelect'

function wrap(ui) {
  return (
    <MemoryRouter>
      <ThemeProvider>{ui}</ThemeProvider>
    </MemoryRouter>
  )
}

describe('kbStatus helpers', () => {
  it('splitTags nettoie, déduplique et ignore le vide', () => {
    expect(splitTags('a, b ; a ,,  c ')).toEqual(['a', 'b', 'c'])
    expect(splitTags('')).toEqual([])
    expect(splitTags(null)).toEqual([])
  })

  it('labelStatutArticle mappe les statuts connus et dégrade proprement', () => {
    expect(labelStatutArticle('publie')).toBe('Publié')
    expect(labelStatutArticle('brouillon')).toBe(KB_STATUT_MAP.brouillon.label)
    expect(labelStatutArticle('inconnu')).toBe('inconnu')
  })
})

describe('FilterSelect (smoke)', () => {
  it('rend les options et la valeur courante', () => {
    render(wrap(
      <FilterSelect
        value="publie"
        onChange={() => {}}
        options={[
          { value: '', label: 'Tous' },
          { value: 'publie', label: 'Publié' },
        ]}
        aria-label="Statut"
      />,
    ))
    const select = screen.getByRole('combobox', { name: 'Statut' })
    expect(select).toBeTruthy()
    expect(select.value).toBe('publie')
    expect(screen.getByText('Publié')).toBeTruthy()
  })
})
