// NTMOB4 — accueil mobile Commercial : redirection desktop, cartes leads/RDV.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isMobileMock } from '../../../test/mobileMocks'
import '../../../test/utilisateur7Mock'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const { crmApiMock, reportingApiMock, installationsApiMock } = vi.hoisted(() => ({
  crmApiMock: { getRelances: vi.fn() },
  reportingApiMock: {
    getCalendar: vi.fn(), approbationsEnAttente: vi.fn(), getNotifications: vi.fn(),
  },
  installationsApiMock: { getMaTournee: vi.fn() },
}))
vi.mock('../../../api/crmApi', () => ({ default: crmApiMock }))
vi.mock('../../../api/reportingApi', () => ({ default: reportingApiMock }))
vi.mock('../../../api/installationsApi', () => ({ default: installationsApiMock }))

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
  reportingApiMock.approbationsEnAttente.mockResolvedValue({ data: { items: [] } })
  reportingApiMock.getNotifications.mockResolvedValue({ data: { factures_impayees: [] } })
  installationsApiMock.getMaTournee.mockResolvedValue({ data: { stops: [] } })
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

  // AERR121 — l'utilisateur de test n'a pas `crm_voir` : le widget ne lit pas
  // les relances ; sa panne est simulée sur la tournée (même chemin `safe`).
  it("panne des relances : jamais « Rien d'urgent », avis + Réessayer", async () => {
    const panne = new Error('Network Error')
    crmApiMock.getRelances.mockRejectedValue(panne)
    installationsApiMock.getMaTournee.mockRejectedValue(panne)
    renderPage()
    expect(await screen.findByText(/Une partie de la journée n'a pas pu être lue/)).toBeInTheDocument()
    expect(await screen.findByText('Lecture impossible')).toBeInTheDocument()
    expect(screen.getAllByRole('button', { name: 'Réessayer' }).length).toBeGreaterThanOrEqual(2)
    expect(screen.queryByText("Rien d'urgent aujourd'hui")).toBeNull()
    expect(screen.queryByText("Aucune relance due aujourd'hui")).toBeNull()
  })

  it('un 403 (droit, module absent) reste silencieux', async () => {
    installationsApiMock.getMaTournee.mockRejectedValue({ response: { status: 403 } })
    renderPage()
    expect(await screen.findByText("Rien d'urgent aujourd'hui")).toBeInTheDocument()
    expect(screen.queryByText(/n'a pas pu être lue/)).toBeNull()
  })
})
