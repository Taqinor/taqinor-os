import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen } from '@testing-library/react'

const ok = (data) => Promise.resolve({ data })

vi.mock('../../api/publicapiApi', () => ({
  default: {
    getKeys: vi.fn(() => ok({ results: [] })),
    getWebhooks: vi.fn(() => ok({ results: [] })),
    getCatalogue: vi.fn(() => ok({ scopes: [], events: [] })),
    getPlan: vi.fn(() => ok(null)),
    getChangelog: vi.fn(() => ok({ results: [
      { id: 1, titre: 'Nouveau tableau de bord', corps: 'Un cockpit direction.', version: '2.4', type: 'feature', breaking: false, date: '2026-07-18T09:00:00Z' },
      { id: 2, titre: 'Correction export', corps: '', version: '2.3', type: 'fix', breaking: false, date: '2026-07-10T09:00:00Z' },
    ] })),
  },
}))

import publicapiApi from '../../api/publicapiApi'
import ApiWebhooksSection from './ApiWebhooksSection'

describe('ApiWebhooksSection — onglet Nouveautés (WIR158)', () => {
  beforeEach(() => { vi.clearAllMocks() })

  it('affiche les dernières entrées du changelog public', async () => {
    render(<ApiWebhooksSection />)
    expect(await screen.findByText('Nouveau tableau de bord')).toBeInTheDocument()
    expect(screen.getByText('Correction export')).toBeInTheDocument()
    expect(screen.getByText('Nouveauté')).toBeInTheDocument()
    expect(screen.getByText('Correctif')).toBeInTheDocument()
    expect(publicapiApi.getChangelog).toHaveBeenCalled()
  })
})
