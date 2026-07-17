import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* ADSDEEP10 — Panneau « Audience & diffusion » : rend les 4 dimensions
   (âge×genre, placements, régions, heures) depuis l'API breakdowns MOCKÉE. */

const mocks = vi.hoisted(() => ({ list: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { breakdowns: { list: mocks.list } },
}))

import BreakdownsPanel from './BreakdownsPanel'

const SAMPLE = [
  { id: 1, dimension: 'age_gender', key: '25-34/f', impressions: 5000, spend: 120, clicks: 60 },
  { id: 2, dimension: 'age_gender', key: '35-44/m', impressions: 3000, spend: 80, clicks: 40 },
  { id: 3, dimension: 'platform', key: 'instagram/reels', impressions: 4000, spend: 100, clicks: 50 },
  { id: 4, dimension: 'region', key: 'Casablanca', impressions: 2500, spend: 70, clicks: 30 },
  { id: 5, dimension: 'hourly', key: '14', impressions: 1200, spend: 40, clicks: 15 },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: SAMPLE })
})

describe('BreakdownsPanel (ADSDEEP10)', () => {
  it('charge les breakdowns de l\'objet ciblé', async () => {
    render(<BreakdownsPanel objectType="campaign" objectId={7} />)
    await waitFor(() => expect(mocks.list).toHaveBeenCalledWith({
      object_type: 'campaign', object_id: 7,
    }))
  })

  it('rend les 4 dimensions avec les données mockées', async () => {
    render(<BreakdownsPanel objectType="campaign" objectId={7} />)
    await screen.findByTestId('ae-breakdowns-panel')
    expect(screen.getByTestId('ae-breakdown-age_gender')).toBeInTheDocument()
    expect(screen.getByTestId('ae-breakdown-platform')).toBeInTheDocument()
    expect(screen.getByTestId('ae-breakdown-region')).toBeInTheDocument()
    expect(screen.getByTestId('ae-breakdown-hourly')).toBeInTheDocument()
    // Âge×genre : deux lignes, avec les clés attendues.
    const ageRows = screen.getAllByTestId('ae-breakdown-age_gender-row')
    expect(ageRows.length).toBe(2)
    expect(ageRows[0]).toHaveTextContent('25-34/f')
    expect(screen.getByText('instagram/reels')).toBeInTheDocument()
    expect(screen.getByText('Casablanca')).toBeInTheDocument()
  })

  it('affiche un état vide quand aucune ventilation', async () => {
    mocks.list.mockResolvedValue({ data: [] })
    render(<BreakdownsPanel objectType="ad" objectId={9} />)
    expect(await screen.findByTestId('ae-breakdowns-empty')).toBeInTheDocument()
  })

  it('ne charge rien sans objectId', async () => {
    render(<BreakdownsPanel objectType="campaign" objectId={null} />)
    await screen.findByTestId('ae-breakdowns-panel')
    expect(mocks.list).not.toHaveBeenCalled()
  })
})
