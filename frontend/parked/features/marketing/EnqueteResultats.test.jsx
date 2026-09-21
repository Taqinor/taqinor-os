import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter, Routes, Route } from 'react-router-dom'

const mocks = vi.hoisted(() => ({
  get: vi.fn(),
  resultats: vi.fn(),
  resultatsExport: vi.fn(),
  downloadBlob: vi.fn(),
  participations: vi.fn(),
}))

vi.mock('../../api/marketingApi', () => ({
  default: {
    downloadBlob: mocks.downloadBlob,
    enquetes: {
      get: mocks.get, resultats: mocks.resultats, resultatsExport: mocks.resultatsExport,
      participations: mocks.participations,
    },
    // PACT109 — route isolée du certificat PDF, publique (jamais un client à mocker
    // ici : c'est une simple URL, téléchargée telle quelle par le navigateur).
    reponsesEnquete: {
      certificatUrl: (reponseId) => `/api/django/marketing/reponses-enquete/${reponseId}/certificat/`,
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
  // Forme RÉELLE de services.participations_enquete : id/contact/score_pct/
  // reussi/date_creation (aucun champ inventé, PACT13).
  mocks.participations.mockResolvedValue({ data: [
    { id: 101, contact: 'Karim Benali', score_pct: 90, reussi: true, date_creation: '2026-08-01T10:00:00Z' },
    { id: 102, contact: 'Anonyme', score_pct: 40, reussi: false, date_creation: '2026-08-02T10:00:00Z' },
  ] })
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

  // ── PACT109 — participations individuelles + certificat (jamais montrés avant) ──
  describe('PACT109 — participations et certificat', () => {
    it('affiche les participations individuelles (contact/score/réussi), pas seulement l\'agrégat', async () => {
      renderScreen()
      await waitFor(() => expect(mocks.participations).toHaveBeenCalledWith('8', undefined))
      const rows = await screen.findAllByTestId('enquete-participation-row')
      expect(rows).toHaveLength(2)
      expect(rows[0]).toHaveTextContent('Karim Benali')
      expect(rows[0]).toHaveTextContent('90%')
      expect(rows[0]).toHaveTextContent('Réussi')
      expect(rows[1]).toHaveTextContent('Anonyme')
      expect(rows[1]).toHaveTextContent('Échoué')
    })

    it('filtre les participations par réussi/échoué via l\'action serveur (pas un filtre client)', async () => {
      renderScreen()
      await screen.findAllByTestId('enquete-participation-row')
      mocks.participations.mockClear()
      mocks.participations.mockResolvedValue({ data: [
        { id: 101, contact: 'Karim Benali', score_pct: 90, reussi: true, date_creation: '2026-08-01T10:00:00Z' },
      ] })
      fireEvent.click(screen.getByTestId('enquete-participations-filtre-true'))
      await waitFor(() => expect(mocks.participations).toHaveBeenCalledWith('8', { reussi: 'true' }))
      await waitFor(() => expect(screen.getAllByTestId('enquete-participation-row')).toHaveLength(1))
    })

    it('n\'affiche AUCUN lien de certificat quand l\'enquête n\'est pas une certification', async () => {
      // mocks.get par défaut ne porte pas est_certification (undefined = false).
      renderScreen()
      await screen.findAllByTestId('enquete-participation-row')
      expect(screen.queryByTestId('enquete-participation-certificat-101')).toBeNull()
    })

    it('affiche le lien de certificat UNIQUEMENT pour une participation réussie d\'une enquête de certification', async () => {
      mocks.get.mockResolvedValue({
        data: {
          id: 8, titre: 'Certification sécurité chantier', token: 'tok8', est_certification: true,
          questions: [],
        },
      })
      renderScreen()
      await screen.findAllByTestId('enquete-participation-row')
      // Réussi (101) -> lien présent, pointant vers la route isolée du serveur.
      const lien = screen.getByTestId('enquete-participation-certificat-101')
      expect(lien).toHaveAttribute('href', '/api/django/marketing/reponses-enquete/101/certificat/')
      // Échoué (102) -> jamais de lien mort.
      expect(screen.queryByTestId('enquete-participation-certificat-102')).toBeNull()
    })

    it('affiche un état vide honnête sans participation', async () => {
      mocks.participations.mockResolvedValue({ data: [] })
      renderScreen()
      await waitFor(() => expect(mocks.participations).toHaveBeenCalled())
      expect(await screen.findByText('Aucune participation')).toBeInTheDocument()
    })
  })
})
