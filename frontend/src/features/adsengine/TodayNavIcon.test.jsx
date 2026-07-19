import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'

/* PUB42 — icône de nav « Aujourd'hui » + badge de comptage (auto-chargée,
   totalement disjointe de Sidebar.jsx — jamais un fichier hors de cette lane
   touché pour l'afficher). */

const mocks = vi.hoisted(() => ({ today: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { today: { get: mocks.today } },
}))

import TodayNavIcon from './TodayNavIcon'

beforeEach(() => { vi.clearAllMocks() })

describe('TodayNavIcon', () => {
  it('compte > 0 -> badge visible avec le nombre', async () => {
    mocks.today.mockResolvedValue({ data: { items: [{ id: 1 }, { id: 2 }], total: 2 } })
    render(<TodayNavIcon />)
    const badge = await screen.findByTestId('ae-nav-today-badge')
    expect(badge).toHaveTextContent('2')
  })

  it('compte > 9 -> plafonné à « 9+ »', async () => {
    mocks.today.mockResolvedValue({ data: { items: [], total: 15 } })
    render(<TodayNavIcon />)
    expect(await screen.findByTestId('ae-nav-today-badge')).toHaveTextContent('9+')
  })

  it('compte = 0 -> aucun badge (jamais un « 0 » affiché)', async () => {
    mocks.today.mockResolvedValue({ data: { items: [], total: 0 } })
    render(<TodayNavIcon />)
    await waitFor(() => expect(mocks.today).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-nav-today-badge')).toBeNull()
  })

  it('échec réseau -> aucun badge (jamais un crash ni un faux compte)', async () => {
    mocks.today.mockRejectedValue(new Error('network'))
    render(<TodayNavIcon />)
    await waitFor(() => expect(mocks.today).toHaveBeenCalled())
    expect(screen.queryByTestId('ae-nav-today-badge')).toBeNull()
  })
})
