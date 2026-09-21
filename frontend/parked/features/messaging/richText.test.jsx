import { describe, it, expect } from 'vitest'
import { render, screen } from '@testing-library/react'
import { parseRichText, renderRichText, applyShortcut } from './richText'

describe('parseRichText (XKB29)', () => {
  it('détecte le gras', () => {
    const blocks = parseRichText('un *mot important* ici')
    expect(blocks[0].tokens.some((t) => t.type === 'bold' && t.value === 'mot important')).toBe(true)
  })

  it('détecte l’italique', () => {
    const blocks = parseRichText('_souligné_')
    expect(blocks[0].tokens[0]).toEqual({ type: 'italic', value: 'souligné' })
  })

  it('détecte le code inline', () => {
    const blocks = parseRichText('`npm run dev`')
    expect(blocks[0].tokens[0]).toEqual({ type: 'code', value: 'npm run dev' })
  })

  it('détecte une liste à puces', () => {
    const blocks = parseRichText('- premier\n- second')
    expect(blocks[0].type).toBe('list')
    expect(blocks[0].items).toHaveLength(2)
  })

  it('détecte une URL nue comme lien', () => {
    const blocks = parseRichText('voir https://taqinor.ma/devis pour détails')
    expect(blocks[0].tokens.some((t) => t.type === 'link' && t.value === 'https://taqinor.ma/devis')).toBe(true)
  })
})

describe('renderRichText — neutralisation XSS', () => {
  it('un payload script est rendu comme texte littéral, jamais exécuté', () => {
    const html = '<script>window.__xss = true</script>'
    render(<div data-testid="out">{renderRichText(html)}</div>)
    // Le texte apparaît tel quel (échappé par React), aucun script n'est injecté/exécuté.
    expect(screen.getByTestId('out').innerHTML).not.toContain('<script>')
    expect(screen.getByTestId('out').textContent).toContain('<script>window.__xss = true</script>')
    expect(window.__xss).toBeUndefined()
  })

  it('*important* se rend en gras', () => {
    render(<div>{renderRichText('*important*')}</div>)
    const strong = screen.getByText('important')
    expect(strong.tagName).toBe('STRONG')
  })

  it('un lien devient cliquable', () => {
    render(<div>{renderRichText('https://taqinor.ma')}</div>)
    const link = screen.getByRole('link', { name: 'https://taqinor.ma' })
    expect(link).toHaveAttribute('href', 'https://taqinor.ma')
    expect(link).toHaveAttribute('target', '_blank')
    expect(link).toHaveAttribute('rel', expect.stringContaining('noreferrer'))
  })

  it('un onclick tapé dans le texte ne devient jamais un attribut DOM', () => {
    render(<div data-testid="out">{renderRichText('<img src=x onerror=alert(1)>')}</div>)
    const out = screen.getByTestId('out')
    expect(out.querySelector('img')).toBeNull()
    expect(out.textContent).toContain('onerror=alert(1)')
  })
})

describe('applyShortcut', () => {
  it('entoure une sélection non vide du marqueur', () => {
    const { text, selectionStart, selectionEnd } = applyShortcut('bonjour tout le monde', 8, 12, '*')
    expect(text).toBe('bonjour *tout* le monde')
    expect(text.slice(selectionStart, selectionEnd)).toBe('*tout*')
  })

  it('insère une paire vide et centre le curseur sans sélection', () => {
    const { text, selectionStart, selectionEnd } = applyShortcut('bonjour ', 8, 8, '`')
    expect(text).toBe('bonjour ``')
    expect(selectionStart).toBe(selectionEnd)
    expect(selectionStart).toBe(9)
  })
})
