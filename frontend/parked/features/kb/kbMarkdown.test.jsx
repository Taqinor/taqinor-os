import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { extractHeadings, KbMarkdownBody } from './kbMarkdown'

describe('extractHeadings (XKB10 — sommaire)', () => {
  it('extrait les titres ATX dans l’ordre, avec un slug unique', () => {
    const corps = [
      '# Introduction',
      'Un paragraphe.',
      '## Étape 1',
      '## Étape 1',
      '### Détail',
    ].join('\n')
    const toc = extractHeadings(corps)
    expect(toc).toEqual([
      { niveau: 1, texte: 'Introduction', slug: 'introduction' },
      { niveau: 2, texte: 'Étape 1', slug: 'etape-1' },
      { niveau: 2, texte: 'Étape 1', slug: 'etape-1-2' },
      { niveau: 3, texte: 'Détail', slug: 'detail' },
    ])
  })

  it('renvoie un tableau vide sans titres', () => {
    expect(extractHeadings('juste du texte')).toEqual([])
    expect(extractHeadings('')).toEqual([])
    expect(extractHeadings(null)).toEqual([])
  })
})

describe('KbMarkdownBody (rendu sûr, jamais de HTML brut)', () => {
  it('rend titres, gras, listes et liens comme des éléments React', () => {
    const corps = [
      '# Titre',
      '*gras* et _italique_ et `code`',
      '- item un',
      '- item deux',
      'Voir https://taqinor.ma pour plus.',
    ].join('\n')
    render(<KbMarkdownBody corps={corps} />)
    expect(screen.getByRole('heading', { level: 1, name: 'Titre' })).toBeTruthy()
    expect(screen.getByText('gras').tagName).toBe('STRONG')
    expect(screen.getByText('italique').tagName).toBe('EM')
    expect(screen.getByText('code').tagName).toBe('CODE')
    expect(screen.getByText('item un')).toBeTruthy()
    expect(screen.getByRole('link', { name: 'https://taqinor.ma' })).toHaveAttribute(
      'href', 'https://taqinor.ma')
  })

  it('n’exécute jamais un script injecté — reste du texte littéral', () => {
    render(<KbMarkdownBody corps={'<script>window.__hacked = true</script>'} />)
    expect(screen.getByText('<script>window.__hacked = true</script>')).toBeTruthy()
    expect(window.__hacked).toBeUndefined()
  })
})
