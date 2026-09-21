import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

vi.mock('../../api/kbApi', () => ({
  default: { listFavoris: vi.fn(), recents: vi.fn() },
}))

import kbApi from '../../api/kbApi'
import FavorisRecentsPanel from './FavorisRecentsPanel'

function wrap(ui) {
  return <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
}

describe('FavorisRecentsPanel (XKB15)', () => {
  it('liste favoris et récents, sélectionne un article', async () => {
    kbApi.listFavoris.mockResolvedValue({
      data: [{ id: 1, article: 10, article_titre: 'Guide onduleur' }],
    })
    kbApi.recents.mockResolvedValue({
      data: [{ id: 20, titre: 'FAQ pompage', statut: 'publie', lu_le: '2026-01-01T10:00:00Z' }],
    })
    const onSelect = vi.fn()
    const user = userEvent.setup()
    render(wrap(<FavorisRecentsPanel onClose={() => {}} onSelect={onSelect} />))

    await waitFor(() => expect(screen.getByText('Guide onduleur')).toBeTruthy())
    expect(screen.getByText('FAQ pompage')).toBeTruthy()

    await user.click(screen.getByText('Guide onduleur'))
    expect(onSelect).toHaveBeenCalledWith({ id: 10 })
  })

  it('dégrade proprement sans favoris ni récents', async () => {
    kbApi.listFavoris.mockResolvedValue({ data: [] })
    kbApi.recents.mockResolvedValue({ data: [] })
    render(wrap(<FavorisRecentsPanel onClose={() => {}} onSelect={() => {}} />))
    await waitFor(() => expect(screen.getByText('Aucun favori')).toBeTruthy())
    expect(screen.getByText('Aucune consultation')).toBeTruthy()
  })
})
