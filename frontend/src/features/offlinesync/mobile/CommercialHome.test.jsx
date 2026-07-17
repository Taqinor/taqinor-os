// NTMOB4 — accueil mobile Commercial : redirection desktop, cartes leads/RDV.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const { crmApiMock, reportingApiMock, isMobileMock } = vi.hoisted(() => ({
  crmApiMock: { getRelances: vi.fn() },
  reportingApiMock: { getCalendar: vi.fn() },
  isMobileMock: vi.fn(() => true),
}))
vi.mock('../../../api/crmApi', () => ({ default: crmApiMock }))
vi.mock('../../../api/reportingApi', () => ({ default: reportingApiMock }))
vi.mock('react-redux', () => ({
  useSelector: (sel) => sel({ auth: { user: { id: 7 } } }),
}))
vi.mock('../../../ui/ResponsiveDialog', async () => {
  const actual = await vi.importActual('../../../ui/ResponsiveDialog')
  return { ...actual, useIsMobile: () => isMobileMock() }
})

import CommercialHome from './CommercialHome'

beforeEach(() => {
  vi.clearAllMocks()
  isMobileMock.mockReturnValue(true)
  crmApiMock.getRelances.mockResolvedValue({
    data: {
      count: 2,
      results: [
        { id: 1, nom: 'Alami', prenom: 'Youssef', telephone: '0600000001', priorite: 'basse' },
        { id: 2, nom: 'Bennani', prenom: 'Sara', telephone: '0600000002', priorite: 'haute' },
      ],
    },
  })
  reportingApiMock.getCalendar.mockResolvedValue({
    data: { events: [{ id: 'ev-1', title: 'Visite chantier', date: '2026-07-17' }] },
  })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/mobile/commercial']}>
      <Routes>
        <Route path="/mobile/commercial" element={<CommercialHome />} />
        <Route path="/dashboard" element={<div>Dashboard desktop</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CommercialHome (NTMOB4)', () => {
  it('redirige vers le dashboard hors viewport mobile', async () => {
    isMobileMock.mockReturnValue(false)
    renderPage()
    await waitFor(() => expect(screen.getByText('Dashboard desktop')).toBeInTheDocument())
    expect(crmApiMock.getRelances).not.toHaveBeenCalled()
  })

  it('affiche les leads du jour triés par priorité (haute avant basse)', async () => {
    renderPage()
    await waitFor(() => expect(crmApiMock.getRelances).toHaveBeenCalledWith({ scope: 'today' }))
    const items = await screen.findAllByRole('button', { name: /Alami|Bennani/ })
    expect(items[0]).toHaveTextContent('Bennani')
    expect(items[1]).toHaveTextContent('Alami')
  })

  it("affiche l'agenda du jour", async () => {
    renderPage()
    expect(await screen.findByText('Visite chantier')).toBeInTheDocument()
  })

  it('propose les raccourcis Nouveau lead / Créer devis / Carte', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /Nouveau lead/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Créer devis/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Carte de mes leads/ })).toBeInTheDocument()
  })
})
