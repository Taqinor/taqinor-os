import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import Breadcrumbs from './Breadcrumbs'

function renderCrumbs(props) {
  return render(
    <MemoryRouter>
      <Breadcrumbs {...props} />
    </MemoryRouter>,
  )
}

describe('Breadcrumbs — I137 accessible + tronqué', () => {
  it('rend un nav[aria-label] (point de repère accessible)', () => {
    const { container } = renderCrumbs({ pathname: '/ventes/devis' })
    const nav = container.querySelector('nav.breadcrumbs')
    expect(nav).toBeInTheDocument()
    expect(nav).toHaveAttribute('aria-label')
  })

  it('le dernier segment (page courante) porte aria-current="page" et n’est pas un lien', () => {
    renderCrumbs({ pathname: '/ventes/devis' })
    const current = screen.getByText('Devis')
    expect(current).toHaveAttribute('aria-current', 'page')
    expect(current.tagName.toLowerCase()).not.toBe('a')
  })

  it('tronque au MILIEU les chemins longs : « … » + tooltip listant les segments masqués', () => {
    const crumbs = [
      { label: 'Niveau A', to: '/a' },
      { label: 'Niveau B', to: '/a/b' },
      { label: 'Niveau C', to: '/a/b/c' },
      { label: 'Niveau D', to: '/a/b/c/d' },
      { label: 'Page courante', to: '/a/b/c/d/e', current: true },
    ]
    const { container } = renderCrumbs({ crumbs })
    // Un débordement « … » apparaît.
    const overflow = container.querySelector('.breadcrumb-overflow')
    expect(overflow).toBeInTheDocument()
    expect(overflow.textContent).toContain('…')
    // Tooltip (title) = libellés masqués complets.
    expect(overflow.getAttribute('title')).toMatch(/Niveau B/)
    expect(overflow.getAttribute('title')).toMatch(/Niveau C/)
    // Le premier, l'avant-dernier et le courant restent visibles.
    expect(screen.getByText('Niveau A')).toBeInTheDocument()
    expect(screen.getByText('Niveau D')).toBeInTheDocument()
    expect(screen.getByText('Page courante')).toHaveAttribute('aria-current', 'page')
    // Les segments masqués ne sont PAS dans le DOM visible.
    expect(screen.queryByText('Niveau B')).not.toBeInTheDocument()
    expect(screen.queryByText('Niveau C')).not.toBeInTheDocument()
  })

  it('ne tronque PAS quand il y a peu de segments', () => {
    const { container } = renderCrumbs({ pathname: '/ventes/devis' })
    expect(container.querySelector('.breadcrumb-overflow')).not.toBeInTheDocument()
  })

  it('un libellé long porte un title (info-bulle plein libellé)', () => {
    const longLabel = 'Un libellé de page particulièrement long qui doit être tronqué visuellement'
    const crumbs = [{ label: longLabel, to: '/x', current: true }]
    renderCrumbs({ crumbs })
    expect(screen.getByText(longLabel)).toHaveAttribute('title', longLabel)
  })
})
