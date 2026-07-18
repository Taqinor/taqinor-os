import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  inscriptionsList: vi.fn(),
  pointer: vi.fn(),
  badgePdf: vi.fn(),
  segmentsCreate: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    downloadBlob: mocks.downloadBlob,
    evenements: { get: mocks.get },
    inscriptionsEvenement: {
      list: mocks.inscriptionsList, pointer: mocks.pointer, badgePdf: mocks.badgePdf,
    },
    segments: { create: mocks.segmentsCreate },
  },
}))

import EvenementDetail from './EvenementDetail'

const renderScreen = () => render(
  <MemoryRouter initialEntries={['/marketing/evenements/4']}>
    <Routes>
      <Route path="/marketing/evenements/:id" element={<EvenementDetail />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({ data: { id: 4, nom: 'SIAM 2026' } })
  mocks.inscriptionsList.mockResolvedValue({
    data: [
      { id: 1, nom: 'Ahmed', email: 'ahmed@x.ma', statut: 'inscrit', statut_display: 'Inscrit' },
      { id: 2, nom: 'Fatima', email: '', statut: 'present', statut_display: 'Présent' },
    ],
  })
})

describe('EvenementDetail', () => {
  it('affiche les inscrits avec leur statut', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.inscriptionsList).toHaveBeenCalledWith({ evenement: '4' }))
    expect(await screen.findByText('Ahmed')).toBeInTheDocument()
    expect(screen.getByText('Fatima')).toBeInTheDocument()
  })

  it('le check-in appelle pointer() et recharge la liste', async () => {
    mocks.pointer.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getAllByTestId('inscription-pointer')[0])
    await waitFor(() => expect(mocks.pointer).toHaveBeenCalledWith(1))
    await waitFor(() => expect(mocks.inscriptionsList).toHaveBeenCalledTimes(2))
  })

  it('un présent ne montre plus le bouton check-in', async () => {
    renderScreen()
    await screen.findByText('Fatima')
    // Une seule ligne (Ahmed) a le bouton check-in, pas Fatima (déjà présente).
    expect(screen.getAllByTestId('inscription-pointer')).toHaveLength(1)
  })

  it('« Badge / QR » télécharge le PDF du badge (XMKT29/ZMKT19)', async () => {
    const blob = new Blob(['%PDF'], { type: 'application/pdf' })
    mocks.badgePdf.mockResolvedValue({ data: blob })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getAllByTestId('inscription-badge')[0])
    await waitFor(() => expect(mocks.badgePdf).toHaveBeenCalledWith(1))
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, 'badge-Ahmed.pdf')
  })

  it("« Créer le segment présents » pose regles: {evenement_present}", async () => {
    mocks.segmentsCreate.mockResolvedValue({ data: { id: 99 } })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getByTestId('evenement-segment-presents'))
    await waitFor(() => expect(mocks.segmentsCreate).toHaveBeenCalledWith({
      nom: 'Présents — SIAM 2026', regles: { evenement_present: 4 },
    }))
    expect(await screen.findByText(/Segment « Présents » créé/)).toBeInTheDocument()
  })
})
