import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup } from '@testing-library/react'
import userEvent from '@testing-library/user-event'

import AnnoncesTab from './AnnoncesTab'
import { renderMarkdownSimple } from '../../lib/markdownSimple'

afterEach(() => {
  cleanup()
  vi.clearAllMocks()
})

const ANNONCES = [
  {
    id: 1,
    titre: 'Nouveau moteur de devis',
    corps: '## Nouveautés\n- PDF une page\n- **Étude** incluse',
    lu: false,
  },
  { id: 2, titre: 'Ancienne nouveauté', corps: 'Texte simple', lu: true },
]

describe('AnnoncesTab — NTADM19', () => {
  it('affiche un état vide explicite sans annonce', () => {
    render(<AnnoncesTab annonces={[]} />)
    expect(screen.getByTestId('annonces-vide')).toBeInTheDocument()
  })

  it('liste les annonces et distingue les non lues', () => {
    render(<AnnoncesTab annonces={ANNONCES} />)
    expect(screen.getByText('Nouveau moteur de devis')).toBeInTheDocument()
    expect(screen.getByTestId('annonce-1')).toHaveAttribute('data-lu', '0')
    expect(screen.getByTestId('annonce-2')).toHaveAttribute('data-lu', '1')
  })

  it('rend le markdown simple (titre, liste, gras)', () => {
    render(<AnnoncesTab annonces={[ANNONCES[0]]} />)
    expect(screen.getByText('Nouveautés')).toBeInTheDocument()
    expect(screen.getByText('PDF une page')).toBeInTheDocument()
    // Le gras est un vrai <strong>, jamais du HTML injecté.
    expect(screen.getByText('Étude').tagName).toBe('STRONG')
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
  })

  it('n\'offre « Marquer comme lu » que sur une annonce non lue', async () => {
    const onMarquerLu = vi.fn()
    render(<AnnoncesTab annonces={ANNONCES} onMarquerLu={onMarquerLu} />)
    const boutons = screen.getAllByRole('button', { name: /Marquer/ })
    expect(boutons).toHaveLength(1)
    await userEvent.click(boutons[0])
    expect(onMarquerLu).toHaveBeenCalledWith(1)
  })

  it('ne rend jamais de HTML brut (pas d\'injection)', () => {
    const { container } = render(<AnnoncesTab annonces={[{
      id: 9, titre: 'Test', lu: true,
      corps: '<img src=x onerror="alert(1)">',
    }]} />)
    // La balise est affichée comme du TEXTE, jamais interprétée.
    expect(container.querySelector('img')).toBeNull()
    expect(screen.getByText(/<img src=x/)).toBeInTheDocument()
  })
})

describe('renderMarkdownSimple', () => {
  it('renvoie un tableau vide pour un corps vide', () => {
    expect(renderMarkdownSimple('')).toEqual([])
    expect(renderMarkdownSimple(null)).toEqual([])
  })

  it('groupe les puces consécutives en une seule liste', () => {
    render(<div>{renderMarkdownSimple('- a\n- b\n\ntexte')}</div>)
    expect(screen.getAllByRole('list')).toHaveLength(1)
    expect(screen.getAllByRole('listitem')).toHaveLength(2)
    expect(screen.getByText('texte')).toBeInTheDocument()
  })
})
