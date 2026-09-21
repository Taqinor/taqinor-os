import { describe, it, expect, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { ThemeProvider } from '../../design/ThemeProvider.jsx'

vi.mock('../../api/kbApi', () => ({
  default: {
    rapportTopConsultes: vi.fn(),
    rapportMoinsConsultes: vi.fn(),
    rapportLacunesConnaissance: vi.fn(),
  },
}))

import kbApi from '../../api/kbApi'
import KbStatsPanel from './KbStatsPanel'

function wrap(ui) {
  return <MemoryRouter><ThemeProvider>{ui}</ThemeProvider></MemoryRouter>
}

describe('KbStatsPanel (XKB16)', () => {
  it('affiche top/moins consultés + lacunes de connaissance', async () => {
    kbApi.rapportTopConsultes.mockResolvedValue({ data: [{ id: 1, titre: 'Guide A', vues: 42 }] })
    kbApi.rapportMoinsConsultes.mockResolvedValue({ data: [{ id: 2, titre: 'Guide B', vues: 0 }] })
    kbApi.rapportLacunesConnaissance.mockResolvedValue({ data: [{ terme_norm: 'onduleur hybride', occurrences: 5 }] })

    render(wrap(<KbStatsPanel onClose={() => {}} />))

    await waitFor(() => expect(screen.getByText('Guide A')).toBeTruthy())
    expect(screen.getByText('42 vue(s)')).toBeTruthy()
    expect(screen.getByText('Guide B')).toBeTruthy()
    expect(screen.getByText('onduleur hybride')).toBeTruthy()
    expect(screen.getByText('5×')).toBeTruthy()
  })

  it('dégrade proprement sans données', async () => {
    kbApi.rapportTopConsultes.mockResolvedValue({ data: [] })
    kbApi.rapportMoinsConsultes.mockResolvedValue({ data: [] })
    kbApi.rapportLacunesConnaissance.mockResolvedValue({ data: [] })
    render(wrap(<KbStatsPanel onClose={() => {}} />))
    await waitFor(() => expect(screen.getByText('Pas encore de données')).toBeTruthy())
  })
})
