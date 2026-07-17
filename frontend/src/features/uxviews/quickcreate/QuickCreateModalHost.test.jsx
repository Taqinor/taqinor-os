// NTUX10 — QuickCreateModalHost : écoute l'événement quick-create et monte
// le modal correspondant, sans navigation.
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'

vi.mock('../../../pages/crm/leads/LeadExpressModal', () => ({
  default: ({ onSaved }) => <div data-testid="mock-lead-modal"><button onClick={onSaved}>Sauver lead</button></div>,
}))
vi.mock('../../../pages/ventes/ClientQuickCreateModal', () => ({
  default: ({ open, onCreated }) => (open ? <div data-testid="mock-client-modal"><button onClick={onCreated}>Sauver client</button></div> : null),
}))
vi.mock('../../../components/ProduitQuickCreateModal', () => ({
  default: ({ open, onCreated }) => (open ? <div data-testid="mock-produit-modal"><button onClick={onCreated}>Sauver produit</button></div> : null),
}))
vi.mock('./TicketQuickCreateModal', () => ({
  default: ({ open, onCreated }) => (open ? <div data-testid="mock-ticket-modal"><button onClick={onCreated}>Sauver ticket</button></div> : null),
}))
vi.mock('../../../ui/confirm', () => ({ toast: { success: vi.fn() } }))

import QuickCreateModalHost from './QuickCreateModalHost'
import { openQuickCreate } from './quickCreateEvents'
import { toast } from '../../../ui/confirm'

afterEach(() => cleanup())

describe('QuickCreateModalHost (NTUX10)', () => {
  it('ne rend rien tant qu\'aucun événement quick-create n\'a été reçu', () => {
    render(<QuickCreateModalHost />)
    expect(screen.queryByTestId('mock-lead-modal')).not.toBeInTheDocument()
  })

  it('openQuickCreate("lead") monte LeadExpressModal', () => {
    render(<QuickCreateModalHost />)
    act(() => openQuickCreate('lead'))
    expect(screen.getByTestId('mock-lead-modal')).toBeInTheDocument()
  })

  it('openQuickCreate("ticket") monte TicketQuickCreateModal', () => {
    render(<QuickCreateModalHost />)
    act(() => openQuickCreate('ticket'))
    expect(screen.getByTestId('mock-ticket-modal')).toBeInTheDocument()
  })

  it('la sauvegarde ferme le modal et affiche un toast de succès', () => {
    render(<QuickCreateModalHost />)
    act(() => openQuickCreate('client'))
    act(() => screen.getByText('Sauver client').click())
    expect(toast.success).toHaveBeenCalledWith('Client créé.')
    expect(screen.queryByTestId('mock-client-modal')).not.toBeInTheDocument()
  })

  it('un second événement change le modal affiché (un seul à la fois)', () => {
    render(<QuickCreateModalHost />)
    act(() => openQuickCreate('produit'))
    expect(screen.getByTestId('mock-produit-modal')).toBeInTheDocument()
    act(() => openQuickCreate('ticket'))
    expect(screen.queryByTestId('mock-produit-modal')).not.toBeInTheDocument()
    expect(screen.getByTestId('mock-ticket-modal')).toBeInTheDocument()
  })
})
