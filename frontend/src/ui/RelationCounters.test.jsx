import { describe, it, expect, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import RelationCounters from './RelationCounters'

/* VX159 — le composant rend des badges cliquables vers une liste PRÉ-FILTRÉE
   et n'invente jamais un compteur vide. */

function renderCounters(counters) {
  return render(
    <MemoryRouter>
      <RelationCounters counters={counters} />
    </MemoryRouter>,
  )
}

afterEach(cleanup)

describe('VX159 — RelationCounters', () => {
  it('affiche chaque compteur avec son nombre et son libellé', () => {
    renderCounters([
      { key: 'devis', label: 'devis', count: 3, to: '/ventes/devis?client=5' },
      { key: 'factures', label: 'factures', count: 1, to: '/ventes/factures?client=5' },
    ])
    expect(screen.getByText('3')).toBeInTheDocument()
    expect(screen.getByText('devis')).toBeInTheDocument()
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('factures')).toBeInTheDocument()
  })

  it('clic → lien vers la liste cible PRÉ-FILTRÉE', () => {
    renderCounters([{ key: 'devis', label: 'devis', count: 3, to: '/ventes/devis?client=5' }])
    const link = screen.getByRole('listitem')
    expect(link.tagName.toLowerCase()).toBe('a')
    expect(link).toHaveAttribute('href', '/ventes/devis?client=5')
  })

  it('rend null si aucun compteur affichable (jamais un 0 inventé)', () => {
    const { container } = renderCounters([{ key: 'x', label: 'x', count: null }])
    expect(container.firstChild).toBeNull()
  })
})
