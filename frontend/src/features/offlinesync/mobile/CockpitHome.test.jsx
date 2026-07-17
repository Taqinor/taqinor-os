// NTMOB5 — cockpit mobile Dirigeant : KPIs + approbations en attente.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const { reportingApiMock, installationsApiMock, isMobileMock } = vi.hoisted(() => ({
  reportingApiMock: {
    getDashboard: vi.fn(),
    getPipeline: vi.fn(),
    approbationsEnAttente: vi.fn(),
  },
  installationsApiMock: { getInstallations: vi.fn() },
  isMobileMock: vi.fn(() => true),
}))
vi.mock('../../../api/reportingApi', () => ({ default: reportingApiMock }))
vi.mock('../../../api/installationsApi', () => ({ default: installationsApiMock }))
vi.mock('../../../ui/ResponsiveDialog', async () => {
  const actual = await vi.importActual('../../../ui/ResponsiveDialog')
  return { ...actual, useIsMobile: () => isMobileMock() }
})

import CockpitHome from './CockpitHome'

beforeEach(() => {
  vi.clearAllMocks()
  isMobileMock.mockReturnValue(true)
  reportingApiMock.getDashboard.mockResolvedValue({
    data: {
      ca_mensuel: [{ mois: 'Jun 2026', ca: 100000 }, { mois: 'Jul 2026', ca: 125000 }],
      statuts_factures: [{ name: 'En retard', value: 3 }, { name: 'Payée', value: 10 }],
    },
  })
  reportingApiMock.getPipeline.mockResolvedValue({
    data: { prevision_ponderee: '45000.00' },
  })
  installationsApiMock.getInstallations.mockResolvedValue({ data: { count: 5, results: [] } })
  reportingApiMock.approbationsEnAttente.mockResolvedValue({
    data: {
      items: [
        { source: 'contrats', id: 1, libelle: 'Contrat X — étape 1', lien: '/contrats/1' },
      ],
    },
  })
})

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/mobile/cockpit']}>
      <Routes>
        <Route path="/mobile/cockpit" element={<CockpitHome />} />
        <Route path="/dashboard" element={<div>Dashboard desktop</div>} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CockpitHome (NTMOB5)', () => {
  it('redirige vers le dashboard hors viewport mobile', async () => {
    isMobileMock.mockReturnValue(false)
    renderPage()
    await waitFor(() => expect(screen.getByText('Dashboard desktop')).toBeInTheDocument())
    expect(reportingApiMock.getDashboard).not.toHaveBeenCalled()
  })

  it('affiche le CA du mois (dernier mois de ca_mensuel)', async () => {
    renderPage()
    expect(await screen.findByText('CA du mois')).toBeInTheDocument()
    await waitFor(() => expect(screen.getByText(/125\s?000,00\s?MAD/)).toBeInTheDocument())
  })

  it('affiche le nombre de chantiers en cours et de factures en retard', async () => {
    renderPage()
    await waitFor(() => expect(installationsApiMock.getInstallations)
      .toHaveBeenCalledWith({ statut: 'en_cours', page_size: 1 }))
    expect(await screen.findByText('Chantiers en cours')).toBeInTheDocument()
    expect(screen.getByText('Factures en retard')).toBeInTheDocument()
  })

  it('liste chaque approbation en attente, ouvrable', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /Contrat X — étape 1/ })).toBeInTheDocument()
  })
})
