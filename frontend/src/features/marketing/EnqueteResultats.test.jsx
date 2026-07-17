import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  resultats: vi.fn(),
  resultatsExport: vi.fn(),
  downloadBlob: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    downloadBlob: mocks.downloadBlob,
    enquetes: {
      get: mocks.get, resultats: mocks.resultats, resultatsExport: mocks.resultatsExport,
    },
  },
}))

import EnqueteResultats from './EnqueteResultats'

const renderScreen = () => render(
  <MemoryRouter initialEntries={['/marketing/enquetes/8']}>
    <Routes>
      <Route path="/marketing/enquetes/:id" element={<EnqueteResultats />} />
    </Routes>
  </MemoryRouter>,
)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockResolvedValue({
    data: {
      id: 8, titre: 'Satisfaction', token: 'tok8',
      questions: [
        { id: 'q1', libelle: 'Recommanderiez-vous ?', type: 'choix' },
        { id: 'q2', libelle: 'Note NPS', type: 'nps' },
      ],
    },
  })
  mocks.resultats.mockResolvedValue({
    data: {
      q1: { type: 'choix', repartition: { Oui: 8, Non: 2 } },
      q2: { type: 'nps', moyenne: 8.5, n: 10, nps: 40 },
      _completion: { total: 10, completes: 9, taux_completion_pct: 90 },
    },
  })
})

describe('EnqueteResultats', () => {
  it('affiche le taux de complétion et les résultats agrégés par question', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.get).toHaveBeenCalledWith('8'))
    expect(mocks.resultats).toHaveBeenCalledWith('8')
    const completion = await screen.findByTestId('enquete-completion')
    expect(completion).toHaveTextContent('10 réponse(s)')
    expect(completion).toHaveTextContent('90% de complétion')
    const questions = screen.getAllByTestId('enquete-resultat-question')
    expect(questions).toHaveLength(2)
    expect(questions[0]).toHaveTextContent('Oui')
    expect(questions[1]).toHaveTextContent('40')
  })

  it('exporter XLSX télécharge le fichier', async () => {
    const blob = new Blob(['xlsx'], { type: 'application/vnd.openxmlformats' })
    mocks.resultatsExport.mockResolvedValue({ data: blob })
    renderScreen()
    await screen.findByTestId('enquete-completion')
    fireEvent.click(screen.getByTestId('enquete-exporter'))
    await waitFor(() => expect(mocks.resultatsExport).toHaveBeenCalledWith('8'))
    expect(mocks.downloadBlob).toHaveBeenCalledWith(blob, 'participations-8.xlsx')
  })
})
