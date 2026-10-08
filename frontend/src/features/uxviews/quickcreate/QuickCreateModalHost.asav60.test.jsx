// ASAV60 — un ticket créé par ⌘K apparaît en tête de la liste /sav (store).
import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, act } from '@testing-library/react'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

vi.mock('../../../pages/crm/leads/LeadExpressModal', () => ({ default: () => null }))
vi.mock('../../../pages/ventes/ClientQuickCreateModal', () => ({ default: () => null }))
vi.mock('../../../components/ProduitQuickCreateModal', () => ({ default: () => null }))
vi.mock('./TicketQuickCreateModal', () => ({
  default: ({ open, onCreated }) => (open
    ? <button onClick={() => onCreated({ id: 99, reference: 'TK-99' })}>Sauver ticket</button> : null),
}))
vi.mock('../../../ui/confirm', () => ({ toast: { success: vi.fn() } }))

import ticketsReducer from '../../sav/store/ticketsSlice'
import QuickCreateModalHost from './QuickCreateModalHost'
import { openQuickCreate } from './quickCreateEvents'
import { toast } from '../../../ui/confirm'

afterEach(() => cleanup())

describe('QuickCreateModalHost (ASAV60)', () => {
  it('insère le ticket créé en tête de tickets.items', () => {
    const store = configureStore({
      reducer: { tickets: ticketsReducer },
      preloadedState: { tickets: { items: [{ id: 1 }], loading: false, error: null } },
    })
    render(<Provider store={store}><QuickCreateModalHost /></Provider>)
    act(() => openQuickCreate('ticket'))
    act(() => screen.getByText('Sauver ticket').click())
    expect(store.getState().tickets.items.map((t) => t.id)).toEqual([99, 1])
    expect(toast.success).toHaveBeenCalledWith('Ticket créé.')
  })
})
