import { describe, it, expect, vi } from 'vitest'
import { render, screen, fireEvent, waitFor } from '@testing-library/react'
import UtmBuilder, { construireUrlUtm } from './UtmBuilder'

describe('construireUrlUtm — NTMKT25 (logique pure)', () => {
  it('compose une URL avec les seuls UTM renseignés', () => {
    expect(construireUrlUtm('https://exemple.ma/pompage', {
      utm_source: 'linkedin', utm_medium: 'organique',
      utm_campaign: 'pompage-2026', utm_content: '', utm_term: '',
    })).toBe('https://exemple.ma/pompage?utm_source=linkedin&utm_medium=organique&utm_campaign=pompage-2026')
  })

  it('omet les paramètres vides (jamais un utm_term= fantôme)', () => {
    const url = construireUrlUtm('https://exemple.ma', { utm_source: 'x' })
    expect(url).not.toContain('utm_term')
    expect(url).not.toContain('utm_content')
  })

  it('écrase un UTM déjà présent dans l\'URL de base', () => {
    expect(construireUrlUtm('https://exemple.ma/?utm_source=ancien', {
      utm_source: 'nouveau',
    })).toBe('https://exemple.ma/?utm_source=nouveau')
  })

  it('préserve le fragment et les paramètres non-UTM', () => {
    const url = construireUrlUtm('https://exemple.ma/p?ref=abc#offre', {
      utm_campaign: 'c',
    })
    expect(url).toContain('ref=abc')
    expect(url).toContain('utm_campaign=c')
    expect(url.endsWith('#offre')).toBe(true)
  })

  it('complète le schéma manquant et refuse une base vide', () => {
    expect(construireUrlUtm('exemple.ma', {})).toBe('https://exemple.ma/')
    expect(construireUrlUtm('', { utm_source: 'x' })).toBe('')
    expect(construireUrlUtm('   ', {})).toBe('')
  })
})

describe('UtmBuilder — écran', () => {
  it('génère et copie l\'URL sans jamais appeler le backend', async () => {
    const writeText = vi.fn().mockResolvedValue()
    Object.assign(navigator, { clipboard: { writeText } })
    render(<UtmBuilder />)
    expect(screen.getByTestId('utm-copier')).toBeDisabled()
    fireEvent.change(screen.getByTestId('utm-url-base'),
      { target: { value: 'https://exemple.ma/pompage' } })
    fireEvent.change(screen.getByTestId('utm-utm_campaign'),
      { target: { value: 'pompage-2026' } })
    expect(screen.getByTestId('utm-resultat'))
      .toHaveTextContent('utm_campaign=pompage-2026')
    fireEvent.click(screen.getByTestId('utm-copier'))
    await waitFor(() => expect(writeText).toHaveBeenCalledWith(
      'https://exemple.ma/pompage?utm_campaign=pompage-2026'))
    await waitFor(() =>
      expect(screen.getByTestId('utm-copier')).toHaveTextContent('Copiée !'))
  })
})
