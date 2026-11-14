// NTMOB5 — cockpit mobile Dirigeant : KPIs + approbations en attente.
import { describe, it, expect, vi, beforeEach } from 'vitest'
import { isMobileMock } from '../../../test/mobileMocks'
import { render, screen, waitFor } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'
import { Provider } from 'react-redux'
import { configureStore } from '@reduxjs/toolkit'

const { reportingApiMock, installationsApiMock } = vi.hoisted(() => ({
  reportingApiMock: {
    getDashboard: vi.fn(),
    getPipeline: vi.fn(),
    approbationsEnAttente: vi.fn(),
    getNotifications: vi.fn(),
  },
  installationsApiMock: { getInstallations: vi.fn(), getMaTournee: vi.fn() },
}))
vi.mock('../../../api/reportingApi', () => ({ default: reportingApiMock }))
vi.mock('../../../api/installationsApi', () => ({ default: installationsApiMock }))

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

function renderPage(auth) {
  const page = (
    <MemoryRouter initialEntries={['/mobile/cockpit']}>
      <Routes>
        <Route path="/mobile/cockpit" element={<CockpitHome />} />
        <Route path="/dashboard" element={<div>Dashboard desktop</div>} />
      </Routes>
    </MemoryRouter>
  )
  if (!auth) return render(page)
  // Compte connecté : l'état d'auth servi, lu par « À faire aujourd'hui ».
  const store = configureStore({ reducer: { auth: (s = auth) => s } })
  return render(<Provider store={store}>{page}</Provider>)
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

  it('affiche le total serveur de chantiers en cours, pas la longueur de la page lue', async () => {
    // page_size=1 : la page ne porte qu'une ligne, `count` porte les 137 chantiers.
    installationsApiMock.getInstallations.mockResolvedValue({
      data: { count: 137, results: [{ id: 1 }] },
    })
    renderPage()
    expect(await screen.findByText('137')).toBeInTheDocument()
  })

  it('liste chaque approbation en attente, ouvrable', async () => {
    renderPage()
    expect(await screen.findByRole('button', { name: /Contrat X — étape 1/ })).toBeInTheDocument()
  })
})

// ADRG122 — « À faire aujourd'hui » ne lit la tournée (`ma-tournee`) que pour
// un compte auquel le serveur la sert (lecture du module chantiers).
describe("CockpitHome — « À faire aujourd'hui » : la tournée selon le droit (ADRG122)", () => {
  beforeEach(() => {
    reportingApiMock.getNotifications.mockResolvedValue({ data: { factures_impayees: [] } })
    // Un arrêt tel que le serveur le sert (une intervention n'a ni titre ni référence propre).
    installationsApiMock.getMaTournee.mockResolvedValue({
      data: { stops: [{ id: 9, type_intervention: 'controle', installation_reference: 'CH-2026-0009', client_nom: 'Villa Atlas' }] },
    })
  })

  it('sans lecture des interventions (Commercial responsable) : `ma-tournee` jamais demandé', async () => {
    renderPage({ user: { id: 3, portee: 'interne' }, role: 'responsable', role_nom: 'Commercial responsable', permissions: ['ventes_voir', 'ventes_creer', 'users_voir'] })
    // Le widget a rendu ses autres sources : sa décision sur la tournée est prise.
    expect(await screen.findByText('Approbation en attente')).toBeInTheDocument()
    expect(installationsApiMock.getMaTournee).not.toHaveBeenCalled()
    expect(screen.queryByText('Intervention du jour')).toBeNull()
  })

  it('avec le droit (Technicien responsable) : l’intervention du jour reste listée', async () => {
    renderPage({ user: { id: 4, portee: 'interne' }, role: 'responsable', role_nom: 'Technicien responsable', permissions: ['installation_voir', 'intervention_gerer', 'users_voir'] })
    expect(await screen.findByText('Intervention #9')).toBeInTheDocument()
    expect(screen.getByText('Intervention du jour')).toBeInTheDocument()
    expect(installationsApiMock.getMaTournee).toHaveBeenCalledTimes(1)
  })
})
