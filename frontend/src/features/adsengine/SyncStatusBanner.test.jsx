import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* PUB41 — bandeau global de panne/fraîcheur. */

const mocks = vi.hoisted(() => ({ get: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { syncStatus: { get: mocks.get } },
}))

import SyncStatusBanner from './SyncStatusBanner'

beforeEach(() => { vi.clearAllMocks() })

describe('SyncStatusBanner', () => {
  it('rien de stale -> aucun bandeau (jamais un faux positif)', async () => {
    mocks.get.mockResolvedValue({ data: { types: [], stale: false, worst: null } })
    render(<SyncStatusBanner />)
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-sync-banner')).toBeNull()
  })

  it('stale -> bandeau avec type/âge/horodatage', async () => {
    mocks.get.mockResolvedValue({ data: {
      types: [{ type: 'insights', label: 'Insights', age_minutes: 130, last_ok_at: '2026-07-17T10:00:00Z', stale: true }],
      stale: true,
      worst: { type: 'insights', label: 'Insights', age_minutes: 130, last_ok_at: '2026-07-17T10:00:00Z' },
    } })
    render(<SyncStatusBanner />)
    const banner = await screen.findByTestId('ae-sync-banner')
    expect(banner).toHaveTextContent('Meta ne répond plus')
    expect(banner).toHaveTextContent('Insights')
    expect(banner).toHaveTextContent('2 h')
  })

  it('échec réseau -> pas de bandeau (jamais un crash, ni un faux positif)', async () => {
    mocks.get.mockRejectedValue(new Error('network'))
    render(<SyncStatusBanner />)
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-sync-banner')).toBeNull()
  })

  it('jamais connecté (tous types sans historique) -> aucun bandeau', async () => {
    mocks.get.mockResolvedValue({ data: {
      types: [{ type: 'insights', label: 'Insights', age_minutes: null, last_ok_at: null, stale: false }],
      stale: false,
      worst: null,
    } })
    render(<SyncStatusBanner />)
    await waitFor(() => expect(mocks.get).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-sync-banner')).toBeNull()
  })
})
