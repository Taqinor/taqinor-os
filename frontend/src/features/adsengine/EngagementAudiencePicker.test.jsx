import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'

/* ADSDEEP59 — Picker « Audiences d'engagement » : rend le catalogue MOCKÉ,
   montre l'estimation d'audience avant usage, crée sans envoyer de donnée CRM. */

const mocks = vi.hoisted(() => ({
  engagementPresets: vi.fn(),
  createEngagement: vi.fn(),
  deliveryEstimate: vi.fn(),
}))

vi.mock('./adsengineApi', () => ({
  default: {
    audiences: {
      engagementPresets: mocks.engagementPresets,
      createEngagement: mocks.createEngagement,
      deliveryEstimate: mocks.deliveryEstimate,
    },
  },
}))

import EngagementAudiencePicker from './EngagementAudiencePicker'

const PRESETS = [
  { key: 'lead_submitted', label: 'Formulaire soumis', source_type: 'lead', retention_days: 90 },
  { key: 'page_engaged', label: 'A interagi avec la Page', source_type: 'page', retention_days: 730 },
  { key: 'ig_engaged', label: 'A interagi avec le compte Instagram', source_type: 'ig_business', retention_days: 730 },
]

beforeEach(() => {
  vi.clearAllMocks()
  mocks.engagementPresets.mockResolvedValue({ data: { presets: PRESETS } })
  mocks.createEngagement.mockResolvedValue({ data: { preset: 'lead_submitted', audience_id: '901', retention_days: 90 } })
  mocks.deliveryEstimate.mockResolvedValue({ data: { estimate: { estimate_ready: true, estimate_dau: 12000 } } })
})

describe('EngagementAudiencePicker (ADSDEEP59)', () => {
  it('charge et rend le catalogue de presets avec rétention', async () => {
    render(<EngagementAudiencePicker />)
    await screen.findByTestId('ae-engagement-picker')
    expect(mocks.engagementPresets).toHaveBeenCalled()
    expect(screen.getByTestId('ae-engagement-option-lead_submitted')).toBeInTheDocument()
    expect(screen.getByTestId('ae-engagement-option-page_engaged')).toBeInTheDocument()
    const retentions = screen.getAllByTestId('ae-engagement-retention')
    expect(retentions[0]).toHaveTextContent('90')
  })

  it('montre l\'estimation d\'audience AVANT usage', async () => {
    render(<EngagementAudiencePicker targetingSpec={{ geo_locations: { countries: ['MA'] } }} />)
    await screen.findByTestId('ae-engagement-picker')
    fireEvent.click(screen.getByTestId('ae-engagement-estimate-btn'))
    await waitFor(() => expect(mocks.deliveryEstimate).toHaveBeenCalledWith({
      targeting_spec: { geo_locations: { countries: ['MA'] } },
    }))
    expect(await screen.findByTestId('ae-engagement-estimate')).toHaveTextContent('12000')
  })

  it('crée une audience d\'engagement (aucune donnée CRM envoyée)', async () => {
    const onCreated = vi.fn()
    render(<EngagementAudiencePicker onCreated={onCreated} />)
    await screen.findByTestId('ae-engagement-picker')
    fireEvent.click(screen.getByTestId('ae-engagement-option-lead_submitted'))
    fireEvent.click(screen.getByTestId('ae-engagement-create-btn'))
    await waitFor(() => expect(mocks.createEngagement).toHaveBeenCalledWith({
      preset_key: 'lead_submitted',
    }))
    // Le payload ne contient QUE le preset — jamais d'email/téléphone/contact.
    const payload = mocks.createEngagement.mock.calls[0][0]
    expect(Object.keys(payload)).toEqual(['preset_key'])
    await waitFor(() => expect(onCreated).toHaveBeenCalled())
  })

  it('n\'estime pas sans ciblage de base', async () => {
    render(<EngagementAudiencePicker />)
    await screen.findByTestId('ae-engagement-picker')
    fireEvent.click(screen.getByTestId('ae-engagement-estimate-btn'))
    expect(mocks.deliveryEstimate).not.toHaveBeenCalled()
    expect(await screen.findByTestId('ae-engagement-message')).toBeInTheDocument()
  })
})
