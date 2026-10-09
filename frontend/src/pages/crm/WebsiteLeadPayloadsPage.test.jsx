import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

const mocks = vi.hoisted(() => ({ getWebsiteLeadPayloads: vi.fn(), replay: vi.fn() }))

vi.mock('../../api/crmApi', () => ({
  default: {
    getWebsiteLeadPayloads: mocks.getWebsiteLeadPayloads,
    replayWebsiteLeadPayload: mocks.replay,
  },
}))

import WebsiteLeadPayloadsPage from './WebsiteLeadPayloadsPage'

const ok = (id) => ({ id, received_at: '2026-10-01T10:00:00', processed: true, error: '', lead: null })

beforeEach(() => {
  vi.clearAllMocks()
  // 3 payloads sur 2 pages de 2 : le payload en erreur est en page 2.
  mocks.getWebsiteLeadPayloads.mockImplementation((params = {}) => Promise.resolve({
    data: params.page === 2
      ? { count: 3, next: null, results: [{ ...ok(3), error: 'mapping KO' }] }
      : { count: 3, next: 'p2', results: [ok(1), ok(2)] },
  }))
})

describe('WebsiteLeadPayloadsPage (AACQ68)', () => {
  it('le payload en erreur au-delà de la page 1 est affiché, en tête', async () => {
    render(<WebsiteLeadPayloadsPage />)
    expect(await screen.findByText('mapping KO')).toBeInTheDocument()
    await waitFor(() => {
      const rows = screen.getAllByRole('row')
      // rows[0] = en-tête ; le payload en erreur vient en premier.
      expect(rows[1]).toHaveTextContent('mapping KO')
    })
  })
})
