import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* ENG26 — Brief hebdo « que s'est-il passé → pourquoi → suggestion » ; les
   cartes porteuses d'action naviguent vers la boîte d'approbation (ENG25). */

const mocks = vi.hoisted(() => ({ latest: vi.fn() }))

vi.mock('./adsengineApi', () => ({
  default: { brief: { latest: mocks.latest } },
}))

import BriefScreen from './BriefScreen'

const BRIEF = {
  periode: 'Semaine du 6 au 12 juillet 2026',
  resume: '3 leads signés, coût par signature en baisse.',
  items: [
    { id: 1, quoi: 'Dépense +15%', pourquoi: 'Hausse des enchères Casa', suggestion: 'Plafonner à 100 MAD/j', action_id: 42 },
    { id: 2, quoi: 'Créatif fatigué', pourquoi: 'Fréquence 3,2', suggestion: 'Rotation créative' },
  ],
}

const renderAt = (ui) => render(
  <MemoryRouter initialEntries={['/publicite/brief']}>
    <Routes>
      <Route path="/publicite/brief" element={ui} />
      <Route path="/publicite/approbations" element={<div>ÉCRAN APPROBATIONS</div>} />
      <Route path="/publicite/journal" element={<div>ÉCRAN JOURNAL</div>} />
    </Routes>
  </MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.latest.mockResolvedValue({ data: BRIEF })
})

describe('BriefScreen (ENG26)', () => {
  it('affiche le brief structuré quoi → pourquoi → suggestion', async () => {
    renderAt(<BriefScreen />)
    await waitFor(() => expect(mocks.latest).toHaveBeenCalled())
    expect(screen.getByTestId('ae-brief-periode')).toHaveTextContent('Semaine du 6 au 12 juillet 2026')
    expect(screen.getAllByTestId('ae-brief-card')).toHaveLength(2)
    expect(screen.getByText('Dépense +15%')).toBeInTheDocument()
    expect(screen.getByText('Hausse des enchères Casa')).toBeInTheDocument()
    expect(screen.getByText('Plafonner à 100 MAD/j')).toBeInTheDocument()
  })

  it('une carte avec action navigue vers la boîte d\'approbation (ENG25)', async () => {
    renderAt(<BriefScreen />)
    await waitFor(() => expect(mocks.latest).toHaveBeenCalled())
    const links = screen.getAllByTestId('ae-brief-approve-link')
    // Seule la carte 1 porte une action → un seul lien d'approbation.
    expect(links).toHaveLength(1)
    expect(links[0]).toHaveAttribute('href', '/publicite/approbations')
    fireEvent.click(links[0])
    expect(await screen.findByText('ÉCRAN APPROBATIONS')).toBeInTheDocument()
  })

  it('le lien Historique mène au journal (ENG28)', async () => {
    renderAt(<BriefScreen />)
    await waitFor(() => expect(mocks.latest).toHaveBeenCalled())
    const hist = screen.getByTestId('ae-brief-history')
    expect(hist).toHaveAttribute('href', '/publicite/journal')
    fireEvent.click(hist)
    expect(await screen.findByText('ÉCRAN JOURNAL')).toBeInTheDocument()
  })

  it('brief vide → message dédié', async () => {
    mocks.latest.mockResolvedValue({ data: { items: [] } })
    renderAt(<BriefScreen />)
    expect(await screen.findByTestId('ae-brief-empty')).toBeInTheDocument()
  })
})
