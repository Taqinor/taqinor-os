import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { render, screen, cleanup, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

/* WIR257 — reporting multi-vue des campagnes (ZMKT8) et reporting/badges
   événement (ZMKT19/20) étaient construits côté serveur SANS aucun écran.
   Couvre :
   (1) l'onglet Reporting rend les 3 groupby (canal/mois/campagne) avec
       CTR/CTOR/délivrabilité ;
   (2) l'export XLSX part AU MÊME groupby que le tableau affiché ;
   (3) « Imprimer tous les badges (PDF) » télécharge le lot ;
   (4) l'onglet Reporting événement rend ses lignes et exporte en XLSX. */

const mocks = vi.hoisted(() => ({
  campagnesList: vi.fn(),
  campagnesReporting: vi.fn(),
  campagnesReportingExport: vi.fn(),
  downloadBlob: vi.fn(),
  exportCampagnesXlsx: vi.fn(),
  evenementGet: vi.fn(),
  evenementBadgesPdf: vi.fn(),
  evenementReporting: vi.fn(),
  evenementReportingExport: vi.fn(),
  inscriptionsList: vi.fn(),
  billetsList: vi.fn(),
  questionsList: vi.fn(),
  communicationsList: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    downloadBlob: mocks.downloadBlob,
    exportCampagnesXlsx: mocks.exportCampagnesXlsx,
    campagnes: {
      list: mocks.campagnesList,
      reporting: mocks.campagnesReporting,
      reportingExportXlsx: mocks.campagnesReportingExport,
      // WIR258 — sonde IA appelée au montage de CampagneForm.
      genererIaDisponible: () => Promise.resolve({ data: { configured: false } }),
      genererIa: () => Promise.resolve({ data: { ok: false } }),
    },
    evenements: {
      get: mocks.evenementGet,
      badgesPdf: mocks.evenementBadgesPdf,
      reporting: mocks.evenementReporting,
      reportingExportXlsx: mocks.evenementReportingExport,
    },
    listes: { list: () => Promise.resolve({ data: [] }) },
    blocsContenu: { list: () => Promise.resolve({ data: [] }) },
    heatmapEngagement: () => Promise.resolve({
      data: { cellules: [], meilleur: null, total_envois: 0 },
    }),
    inscriptionsEvenement: { list: mocks.inscriptionsList },
    billetsEvenement: { list: mocks.billetsList },
    questionsEvenement: { list: mocks.questionsList },
    communicationsEvenement: { list: mocks.communicationsList },
  },
}))

import CampagnesList from './CampagnesList'
import EvenementDetail from './EvenementDetail'

const LIGNES_CAMPAGNES = [{
  groupe: 'email', delivres: 10, ouverts: 4, cliques: 2, rebonds: 0,
  desinscrits: 1, ctr_pct: 20.0, ctor_pct: 50.0, delivrabilite_pct: 100.0,
}]

const LIGNES_EVENEMENTS = [{
  evenement_id: 1, nom: 'Salon Solaire', type_evenement: 'salon',
  nb_inscrits: 2, nb_confirmes: 2, nb_presents: 1, nb_absents: 1,
  taux_presence_pct: 50.0, recette_theorique_mad: '200.00', nb_leads: 1,
}]

beforeEach(() => {
  mocks.campagnesList.mockResolvedValue({ data: [] })
  mocks.campagnesReporting.mockResolvedValue({ data: LIGNES_CAMPAGNES })
  mocks.campagnesReportingExport.mockResolvedValue({ data: new Blob(['x']) })
  mocks.evenementGet.mockResolvedValue({
    data: { id: 1, nom: 'Salon Solaire', type_evenement: 'salon' },
  })
  mocks.inscriptionsList.mockResolvedValue({ data: [] })
  mocks.billetsList.mockResolvedValue({ data: [] })
  mocks.questionsList.mockResolvedValue({ data: [] })
  mocks.communicationsList.mockResolvedValue({ data: [] })
  mocks.evenementBadgesPdf.mockResolvedValue({ data: new Blob(['pdf']) })
  mocks.evenementReporting.mockResolvedValue({ data: LIGNES_EVENEMENTS })
  mocks.evenementReportingExport.mockResolvedValue({ data: new Blob(['x']) })
})
afterEach(() => { cleanup(); vi.clearAllMocks() })

function renderEvenement() {
  return render(
    <MemoryRouter initialEntries={['/marketing/evenements/1']}>
      <Routes>
        <Route path="/marketing/evenements/:id" element={<EvenementDetail />} />
      </Routes>
    </MemoryRouter>,
  )
}

describe('CampagnesList — WIR257 reporting multi-vue (ZMKT8)', () => {
  it('ne charge le reporting QUE sur son onglet, puis rend les mesures', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><CampagnesList /></MemoryRouter>)
    await waitFor(() => expect(mocks.campagnesList).toHaveBeenCalled())
    expect(mocks.campagnesReporting).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('campagnes-vue-reporting'))
    await waitFor(() => expect(mocks.campagnesReporting)
      .toHaveBeenCalledWith({ groupby: 'canal' }))

    const ligne = within(await screen.findByTestId('reporting-table'))
      .getByTestId('reporting-row')
    expect(ligne).toHaveTextContent('email')
    expect(ligne).toHaveTextContent('20')  // CTR %
    expect(ligne).toHaveTextContent('50')  // CTOR %
  })

  it('recharge sur les 3 groupby et exporte AU MÊME groupby', async () => {
    const user = userEvent.setup()
    render(<MemoryRouter><CampagnesList /></MemoryRouter>)
    await user.click(screen.getByTestId('campagnes-vue-reporting'))
    await waitFor(() => expect(mocks.campagnesReporting).toHaveBeenCalled())

    await user.selectOptions(screen.getByTestId('reporting-groupby'), 'mois')
    await waitFor(() => expect(mocks.campagnesReporting)
      .toHaveBeenCalledWith({ groupby: 'mois' }))
    await user.selectOptions(screen.getByTestId('reporting-groupby'), 'campagne')
    await waitFor(() => expect(mocks.campagnesReporting)
      .toHaveBeenCalledWith({ groupby: 'campagne' }))

    await user.click(screen.getByTestId('reporting-exporter'))
    await waitFor(() => expect(mocks.campagnesReportingExport)
      .toHaveBeenCalledWith({ groupby: 'campagne' }))
    await waitFor(() => expect(mocks.downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob), 'reporting_campagnes_campagne.xlsx'))
  })
})

describe('EvenementDetail — WIR257 badges en lot + reporting (ZMKT19/20)', () => {
  it('télécharge le PDF de TOUS les badges', async () => {
    const user = userEvent.setup()
    renderEvenement()
    await user.click(await screen.findByTestId('inscriptions-badges-lot'))
    await waitFor(() => expect(mocks.evenementBadgesPdf).toHaveBeenCalledWith('1'))
    await waitFor(() => expect(mocks.downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob), 'badges-evenement-1.pdf'))
  })

  it('rend le reporting événement et l’exporte en XLSX', async () => {
    const user = userEvent.setup()
    renderEvenement()
    await screen.findByTestId('evenement-onglet-reporting')
    expect(mocks.evenementReporting).not.toHaveBeenCalled()

    await user.click(screen.getByTestId('evenement-onglet-reporting'))
    await waitFor(() => expect(mocks.evenementReporting).toHaveBeenCalled())

    const ligne = within(await screen.findByTestId('evenement-reporting-table'))
      .getByTestId('evenement-reporting-row')
    expect(ligne).toHaveTextContent('Salon Solaire')
    expect(ligne).toHaveTextContent('200.00')

    await user.click(screen.getByTestId('evenement-reporting-exporter'))
    await waitFor(() => expect(mocks.evenementReportingExport).toHaveBeenCalled())
    await waitFor(() => expect(mocks.downloadBlob).toHaveBeenCalledWith(
      expect.any(Blob), 'reporting_evenements.xlsx'))
  })
})
