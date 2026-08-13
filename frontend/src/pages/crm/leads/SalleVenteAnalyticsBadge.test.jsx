import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor } from '@testing-library/react'
import SalleVenteAnalyticsBadge from './SalleVenteAnalyticsBadge'

vi.mock('../../../api/crmApi', () => ({
  default: { getLeadSalleVenteAnalytics: vi.fn() },
}))

import crmApi from '../../../api/crmApi'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('SalleVenteAnalyticsBadge (NTCRM19)', () => {
  it('affiche le compteur et la dernière vue quand consulté', async () => {
    crmApi.getLeadSalleVenteAnalytics.mockResolvedValue({
      data: { nb_vues: 3, derniere_vue: '2026-08-12T10:00:00Z' },
    })
    render(<SalleVenteAnalyticsBadge leadId={7} />)
    await waitFor(() => expect(screen.getByTestId('salle-vente-analytics-badge')).toBeInTheDocument())
    expect(screen.getByText(/consulté sa salle de vente 3 fois/)).toBeInTheDocument()
  })

  it('n\'affiche rien sans salle de vente', async () => {
    crmApi.getLeadSalleVenteAnalytics.mockResolvedValue({ data: null })
    render(<SalleVenteAnalyticsBadge leadId={7} />)
    await waitFor(() => {})
    expect(screen.queryByTestId('salle-vente-analytics-badge')).toBeNull()
  })

  it('n\'affiche rien quand nb_vues=0', async () => {
    crmApi.getLeadSalleVenteAnalytics.mockResolvedValue({
      data: { nb_vues: 0, derniere_vue: null },
    })
    render(<SalleVenteAnalyticsBadge leadId={7} />)
    await waitFor(() => {})
    expect(screen.queryByTestId('salle-vente-analytics-badge')).toBeNull()
  })

  it('ne casse rien sans leadId', () => {
    render(<SalleVenteAnalyticsBadge leadId={null} />)
    expect(screen.queryByTestId('salle-vente-analytics-badge')).toBeNull()
  })
})
