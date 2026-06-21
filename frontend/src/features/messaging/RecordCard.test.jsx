import { describe, it, expect, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'

const navigate = vi.fn()
vi.mock('react-router-dom', async (orig) => ({
  ...(await orig()),
  useNavigate: () => navigate,
}))

import RecordCard from './RecordCard'

function renderCard(record) {
  return render(<MemoryRouter><RecordCard record={record} /></MemoryRouter>)
}

describe('RecordCard (S19)', () => {
  it('rend le libellé et le sous-titre', () => {
    renderCard({ label: 'Devis DV-2026-001', subtitle: 'M. Reda', url: '/ventes/devis?devis=3' })
    expect(screen.getByText('Devis DV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('M. Reda')).toBeInTheDocument()
  })

  it('navigue en SPA quand l’URL est interne', async () => {
    navigate.mockClear()
    renderCard({ label: 'Lead X', record_type: 'lead', url: '/crm/leads?lead=5' })
    await userEvent.click(screen.getByTestId('record-card'))
    expect(navigate).toHaveBeenCalledWith('/crm/leads?lead=5')
  })

  it('supporte le snapshot serveur (shared_label / shared_url)', () => {
    renderCard({ shared_label: 'Chantier #7', shared_url: '/chantiers' })
    expect(screen.getByText('Chantier #7')).toBeInTheDocument()
  })

  it('ne rend rien sans libellé', () => {
    const { container } = renderCard({ url: '/x' })
    expect(container.firstChild).toBeNull()
  })
})
