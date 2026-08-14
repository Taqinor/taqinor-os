import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import LeadMaturiteBadge from './LeadMaturiteBadge'

vi.mock('../../../api/marketingApi', () => ({
  default: { scoreMaturite: { get: vi.fn() } },
}))

import marketingApi from '../../../api/marketingApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('LeadMaturiteBadge (NTMKT18/19)', () => {
  it('affiche le badge chaud avec le score courant', async () => {
    marketingApi.scoreMaturite.get.mockResolvedValue({
      data: {
        actif: true, valeur: 82,
        historique: [
          { delta: 2, valeur_apres: 82, motif: '', created_at: '2026-08-10T00:00:00Z' },
          { delta: 5, valeur_apres: 80, motif: '', created_at: '2026-08-05T00:00:00Z' },
        ],
      },
    })
    render(<LeadMaturiteBadge leadId={7} />)
    await waitFor(() => expect(screen.getByTestId('lead-maturite-badge')).toBeInTheDocument())
    expect(screen.getByText('Chaud · 82')).toBeInTheDocument()
  })

  it('affiche le badge tiède entre 30 et 69', async () => {
    marketingApi.scoreMaturite.get.mockResolvedValue({
      data: { actif: true, valeur: 45, historique: [] },
    })
    render(<LeadMaturiteBadge leadId={7} />)
    await waitFor(() => expect(screen.getByTestId('lead-maturite-badge')).toBeInTheDocument())
    expect(screen.getByText('Tiède · 45')).toBeInTheDocument()
  })

  it('affiche le badge froid sous 30', async () => {
    marketingApi.scoreMaturite.get.mockResolvedValue({
      data: { actif: true, valeur: 5, historique: [] },
    })
    render(<LeadMaturiteBadge leadId={7} />)
    await waitFor(() => expect(screen.getByTestId('lead-maturite-badge')).toBeInTheDocument())
    expect(screen.getByText('Froid · 5')).toBeInTheDocument()
  })

  it('n\'affiche rien quand le module est désactivé pour la société', async () => {
    marketingApi.scoreMaturite.get.mockResolvedValue({ data: { actif: false, valeur: 0 } })
    render(<LeadMaturiteBadge leadId={7} />)
    await waitFor(() => {})
    expect(screen.queryByTestId('lead-maturite-badge')).toBeNull()
  })

  it('ne casse rien sans leadId', () => {
    render(<LeadMaturiteBadge leadId={null} />)
    expect(screen.queryByTestId('lead-maturite-badge')).toBeNull()
  })

  it('ne casse rien si l\'appel échoue', async () => {
    marketingApi.scoreMaturite.get.mockRejectedValue(new Error('boom'))
    render(<LeadMaturiteBadge leadId={7} />)
    await waitFor(() => {})
    expect(screen.queryByTestId('lead-maturite-badge')).toBeNull()
  })
})
