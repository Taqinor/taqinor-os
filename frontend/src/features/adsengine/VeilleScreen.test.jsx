import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { documentContrat } from '../../test/fixtures/contractSamples'

/* PUB70 + VEIL30 — Veille : bandeau de couverture PAR PAYS (contrat
   veille_couverture.json), onglet « Découverte » par défaut, onglet « Saisie
   manuelle » (pages suivies avec lien profond, observations, cadence). */

const COUVERTURE = documentContrat('adsengine', 'veille_couverture').exemple

const mocks = vi.hoisted(() => ({
  list: vi.fn(), create: vi.fn(), veille: vi.fn(), obsCreate: vi.fn(),
  couverture: vi.fn(), decouvertes: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    competitors: { list: mocks.list, create: mocks.create, veille: mocks.veille },
    competitorObservations: { create: mocks.obsCreate },
    veille: { couverture: mocks.couverture, decouvertes: mocks.decouvertes },
  },
}))

import VeilleScreen from './VeilleScreen'

const renderScreen = () => render(<MemoryRouter><VeilleScreen /></MemoryRouter>)
const ouvrirSaisieManuelle = async () => {
  renderScreen()
  fireEvent.click(screen.getByTestId('ae-veille-onglet-manuel'))
}

const PAGES = [
  { id: 1, name: 'SolaireX', country: 'MA', ad_library_url: 'https://www.facebook.com/ads/library/?view_all_page_id=1' },
]
const VEILLE = {
  finding: {
    reason_fr: "La couverture de l'API Ad Library dépend du pays.",
    couverture_url: '/api/django/adsengine/veille/couverture/',
    automation_status: 'GATED',
  },
  cadence: [{ competitor_id: 1, competitor: 'SolaireX', total: 3, par_semaine: {} }],
  brief_material: [],
}

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: PAGES })
  mocks.veille.mockResolvedValue({ data: VEILLE })
  mocks.create.mockResolvedValue({ data: { id: 2 } })
  mocks.obsCreate.mockResolvedValue({ data: { id: 9 } })
  mocks.couverture.mockResolvedValue({ data: COUVERTURE })
  mocks.decouvertes.mockResolvedValue({ data: { count: 0, results: [] } })
})

describe('VeilleScreen', () => {
  it('bandeau de couverture PAR PAYS et état de l’accès, servis par le serveur', async () => {
    renderScreen()
    const bandeau = await screen.findByTestId('ae-veille-couverture')
    expect(screen.getByTestId('ae-veille-couverture-couvert').textContent).toContain('FR')
    expect(screen.getByTestId('ae-veille-couverture-a_confirmer').textContent).toContain('GB')
    expect(screen.getByTestId('ae-veille-couverture-non_couvert').textContent).toContain('MA')
    expect(screen.getByTestId('ae-veille-acces').dataset.etat).toBe(COUVERTURE.acces.etat)
    expect(bandeau.textContent).not.toMatch(/ne couvre PAS les pubs commerciales/)
  })

  it('« Découverte » est l’onglet par défaut', async () => {
    renderScreen()
    expect(await screen.findByTestId('ae-veille-decouverte')).toBeTruthy()
    expect(screen.queryByTestId('ae-veille-manuel')).toBeNull()
  })

  it('affiche le finding et les pages suivies avec lien profond', async () => {
    await ouvrirSaisieManuelle()
    await waitFor(() => expect(screen.getByTestId('ae-veille-pages')).toBeTruthy())
    expect(screen.getByTestId('ae-veille-finding').textContent).toContain('pays')
    const link = screen.getByTestId('ae-veille-link-1')
    expect(link.getAttribute('href')).toContain('facebook.com/ads/library')
  })

  it('affiche la cadence par concurrent', async () => {
    await ouvrirSaisieManuelle()
    await waitFor(() => expect(screen.getByTestId('ae-veille-cadence')).toBeTruthy())
    expect(screen.getByTestId('ae-veille-cadence').textContent).toContain('SolaireX')
  })

  it('ajoute un concurrent', async () => {
    await ouvrirSaisieManuelle()
    await waitFor(() => expect(screen.getByTestId('ae-veille-page-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-veille-page-name'), { target: { value: 'NouveauX' } })
    fireEvent.click(screen.getByTestId('ae-veille-page-add'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalled())
    expect(mocks.create.mock.calls[0][0].name).toBe('NouveauX')
  })

  it('saisit une observation manuelle', async () => {
    await ouvrirSaisieManuelle()
    await waitFor(() => expect(screen.getByTestId('ae-veille-obs-form')).toBeTruthy())
    fireEvent.change(screen.getByTestId('ae-veille-obs-page'), { target: { value: '1' } })
    fireEvent.change(screen.getByTestId('ae-veille-obs-date'), { target: { value: '2026-07-15' } })
    fireEvent.change(screen.getByTestId('ae-veille-obs-hook'), { target: { value: 'Économisez' } })
    fireEvent.click(screen.getByTestId('ae-veille-obs-add'))
    await waitFor(() => expect(mocks.obsCreate).toHaveBeenCalled())
    expect(mocks.obsCreate.mock.calls[0][0].hook_text).toBe('Économisez')
  })
})
