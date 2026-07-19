import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PUB70 — Veille : finding API, pages suivies avec lien profond, saisie manuelle
   d'observations, cadence. Zéro scraping — tout est piloté par l'API mockée. */

const mocks = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), veille: vi.fn(), obsCreate: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    competitors: { list: mocks.list, create: mocks.create, veille: mocks.veille },
    competitorObservations: { create: mocks.obsCreate },
  },
}))

import VeilleScreen from './VeilleScreen'

const renderScreen = () => render(<MemoryRouter><VeilleScreen /></MemoryRouter>)

const PAGES = [
  { id: 1, name: 'SolaireX', country: 'MA', ad_library_url: 'https://www.facebook.com/ads/library/?view_all_page_id=1' },
]
const VEILLE = {
  finding: { covers_commercial: false, reason_fr: "L'API ne couvre pas le commercial." },
  cadence: [{ competitor_id: 1, competitor: 'SolaireX', total: 3, par_semaine: {} }],
  brief_material: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: PAGES })
  mocks.veille.mockResolvedValue({ data: VEILLE })
  mocks.create.mockResolvedValue({ data: { id: 2 } })
  mocks.obsCreate.mockResolvedValue({ data: { id: 9 } })
})

describe('VeilleScreen', () => {
  it('affiche le finding API et les pages suivies avec lien profond', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-veille-pages')).toBeTruthy())
    expect(screen.getByTestId('ae-veille-finding').textContent).toContain('commercial')
    const link = screen.getByTestId('ae-veille-link-1')
    expect(link.getAttribute('href')).toContain('facebook.com/ads/library')
  })

  it('affiche la cadence par concurrent', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-veille-cadence')).toBeTruthy())
    expect(screen.getByTestId('ae-veille-cadence').textContent).toContain('SolaireX')
  })

  it('ajoute un concurrent', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-veille-page-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-veille-page-name'), { target: { value: 'NouveauX' } })
    fireEvent.click(screen.getByTestId('ae-veille-page-add'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].name).toBe('NouveauX')
  })

  it('saisit une observation manuelle', async () => {
    renderScreen()
    await waitFor(() => expect(screen.getByTestId('ae-veille-obs-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-veille-obs-page'), { target: { value: '1' } })
    fireEvent.change(screen.getByTestId('ae-veille-obs-date'), { target: { value: '2026-07-15' } })
    fireEvent.change(screen.getByTestId('ae-veille-obs-hook'), { target: { value: 'Économisez' } })
    fireEvent.click(screen.getByTestId('ae-veille-obs-add'))
    await waitFor(() => expect(mocks.obsCreate).toHaveBeenCalled())
    expect(mocks.obsCreate.mock.calls[0][0].hook_text).toBe('Économisez')
  })
})
