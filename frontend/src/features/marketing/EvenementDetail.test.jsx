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
  // WIR162 — billets/questions/communications (chargement paresseux par
  // onglet, cf. EvenementDetail.jsx) : jamais appelés par les tests existants
  // (qui ne quittent jamais l'onglet Inscrits par défaut), mais nécessaires
  // pour les nouveaux tests ci-dessous.
  billetsList: vi.fn(), billetsCreate: vi.fn(), billetsRemove: vi.fn(),
  questionsList: vi.fn(), questionsCreate: vi.fn(), questionsRemove: vi.fn(),
  communicationsList: vi.fn(), communicationsCreate: vi.fn(), communicationsRemove: vi.fn(),
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
    billetsEvenement: { list: mocks.billetsList, create: mocks.billetsCreate, remove: mocks.billetsRemove },
    questionsEvenement: { list: mocks.questionsList, create: mocks.questionsCreate, remove: mocks.questionsRemove },
    communicationsEvenement: {
      list: mocks.communicationsList, create: mocks.communicationsCreate, remove: mocks.communicationsRemove,
    },
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
  mocks.billetsList.mockResolvedValue({ data: [] })
  mocks.questionsList.mockResolvedValue({ data: [] })
  mocks.communicationsList.mockResolvedValue({ data: [] })
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

/* WIR162 — onglets Billets/Questions/Communications : chargement paresseux
   (aucun appel avant l'ouverture de l'onglet) + création/suppression. */
describe('EvenementDetail — billets/questions/communications (WIR162)', () => {
  it("l'onglet Inscrits (par défaut) n'appelle aucun des 3 nouveaux endpoints", async () => {
    renderScreen()
    await screen.findByText('Ahmed')
    expect(mocks.billetsList).not.toHaveBeenCalled()
    expect(mocks.questionsList).not.toHaveBeenCalled()
    expect(mocks.communicationsList).not.toHaveBeenCalled()
  })

  it('crée un billet depuis l’onglet Billets', async () => {
    mocks.billetsCreate.mockResolvedValue({ data: { id: 10 } })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getByTestId('evenement-onglet-billets'))
    await waitFor(() => expect(mocks.billetsList).toHaveBeenCalledWith({ evenement: '4' }))

    fireEvent.change(screen.getByTestId('billet-libelle'), { target: { value: 'VIP' } })
    fireEvent.change(screen.getByTestId('billet-prix'), { target: { value: '500' } })
    fireEvent.click(screen.getByTestId('billet-ajouter'))

    await waitFor(() => expect(mocks.billetsCreate).toHaveBeenCalledWith({
      evenement: 4, libelle: 'VIP', prix_ttc_mad: 500, quota: null,
    }))
    await waitFor(() => expect(mocks.billetsList).toHaveBeenCalledTimes(2))
  })

  it('supprime un billet existant', async () => {
    mocks.billetsList.mockResolvedValue({ data: [{ id: 10, libelle: 'VIP', prix_ttc_mad: '500.00' }] })
    mocks.billetsRemove.mockResolvedValue({ data: {} })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getByTestId('evenement-onglet-billets'))
    await screen.findByText('VIP')
    fireEvent.click(screen.getByTestId('billet-supprimer'))
    await waitFor(() => expect(mocks.billetsRemove).toHaveBeenCalledWith(10))
  })

  it('crée une question depuis l’onglet Questions', async () => {
    mocks.questionsCreate.mockResolvedValue({ data: { id: 20 } })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getByTestId('evenement-onglet-questions'))
    await waitFor(() => expect(mocks.questionsList).toHaveBeenCalledWith({ evenement: '4' }))

    fireEvent.change(screen.getByTestId('question-libelle'), { target: { value: 'Combien de personnes ?' } })
    fireEvent.click(screen.getByTestId('question-obligatoire'))
    fireEvent.click(screen.getByTestId('question-ajouter'))

    await waitFor(() => expect(mocks.questionsCreate).toHaveBeenCalledWith({
      evenement: 4, libelle: 'Combien de personnes ?', type_question: 'texte',
      obligatoire: true, portee: 'par_inscrit',
    }))
  })

  it('planifie une communication depuis l’onglet Communications', async () => {
    mocks.communicationsCreate.mockResolvedValue({ data: { id: 30 } })
    renderScreen()
    await screen.findByText('Ahmed')
    fireEvent.click(screen.getByTestId('evenement-onglet-communications'))
    await waitFor(() => expect(mocks.communicationsList).toHaveBeenCalledWith({ evenement: '4' }))

    fireEvent.change(screen.getByTestId('communication-intervalle'), { target: { value: '-2' } })
    fireEvent.change(screen.getByTestId('communication-gabarit'), { target: { value: 'Rappel : à demain !' } })
    fireEvent.click(screen.getByTestId('communication-ajouter'))

    await waitFor(() => expect(mocks.communicationsCreate).toHaveBeenCalledWith({
      evenement: 4, canal: 'email', gabarit: 'Rappel : à demain !',
      intervalle: -2, unite_intervalle: 'jours',
    }))
  })
})
