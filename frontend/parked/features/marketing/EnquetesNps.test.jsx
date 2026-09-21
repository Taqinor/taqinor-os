import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PACT107 — Enquêtes NPS post-installation (EnqueteNPSViewSet,
   /marketing/enquetes-nps/ ; actions repondre/score). Forme mockée = exactement
   EnqueteNPSSerializer (id/client_id/chantier_id/score/commentaire/statut/
   categorie(lecture seule, calculée serveur)/envoi_reel/envoyee_le/repondue_le).
   Le score consolidé vient de l'action serveur `score`, jamais recalculé ici. */

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), repondre: vi.fn(), score: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    enquetesNps: { list: mocks.list, create: mocks.create, repondre: mocks.repondre, score: mocks.score },
  },
}))

import EnquetesNps from './EnquetesNps'

const renderScreen = () => render(<MemoryRouter><EnquetesNps /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, client_id: 501, chantier_id: 90, score: null, commentaire: '',
      statut: 'envoyee', categorie: null, envoi_reel: false,
      envoyee_le: '2026-08-01T09:00:00Z', repondue_le: null },
    { id: 2, client_id: 502, chantier_id: null, score: 10, commentaire: 'Parfait',
      statut: 'repondue', categorie: 'promoteur', envoi_reel: false,
      envoyee_le: '2026-07-20T09:00:00Z', repondue_le: '2026-07-21T09:00:00Z' },
  ] })
  mocks.create.mockResolvedValue({ data: { id: 3 } })
  mocks.score.mockResolvedValue({ data: { nps: 50, total: 2, promoteurs: 1, passifs: 0, detracteurs: 0 } })
  mocks.repondre.mockResolvedValue({ data: {
    id: 1, client_id: 501, chantier_id: 90, score: 9, commentaire: 'Très bien',
    statut: 'repondue', categorie: 'promoteur', envoi_reel: false,
    envoyee_le: '2026-08-01T09:00:00Z', repondue_le: '2026-08-05T09:00:00Z',
  } })
})

describe('EnquetesNps (PACT107)', () => {
  it('affiche le score NPS consolidé venant de l\'API (jamais recalculé)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.score).toHaveBeenCalled())
    expect(await screen.findByTestId('nps-score-valeur')).toHaveTextContent('50')
    expect(screen.getByTestId('nps-score')).toHaveTextContent('1 promoteur')
  })

  it('affiche les enquêtes existantes avec leur catégorie réelle', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByText('Client #501')).toBeInTheDocument()
    expect(screen.getByText('Client #502')).toBeInTheDocument()
    expect(screen.getByText('Promoteur')).toBeInTheDocument()
    expect(screen.getByText('Parfait')).toBeInTheDocument()
  })

  it('envoie une nouvelle enquête NPS pour un client (chantier optionnel)', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('nps-client-id'), { target: { value: '888' } })
    fireEvent.click(screen.getByText("Envoyer l'enquête"))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ client_id: 888 }))
  })

  it('enregistre une réponse (note + commentaire) pour une enquête envoyée', async () => {
    renderScreen()
    await screen.findAllByTestId('nps-row')
    fireEvent.click(screen.getByTestId('nps-repondre-1'))
    fireEvent.change(screen.getByTestId('nps-repondre-score-1'), { target: { value: '9' } })
    fireEvent.change(screen.getByTestId('nps-repondre-commentaire-1'), { target: { value: 'Très bien' } })
    fireEvent.click(screen.getByTestId('nps-repondre-confirm-1'))
    await waitFor(() => expect(mocks.repondre).toHaveBeenCalledWith(
      1, { score: 9, commentaire: 'Très bien' }))
    // La catégorie affichée vient de la réponse SERVEUR, jamais dérivée côté client.
    await waitFor(() => expect(screen.getAllByTestId('nps-row')[0]).toHaveTextContent('Promoteur'))
  })

  it('une enquête déjà répondue n\'a plus de bouton « Enregistrer une réponse »', async () => {
    renderScreen()
    await screen.findAllByTestId('nps-row')
    expect(screen.queryByTestId('nps-repondre-2')).toBeNull()
  })

  it('aucune réponse encore : le score affiche un état vide honnête', async () => {
    mocks.score.mockResolvedValue({ data: { nps: null, total: 0, promoteurs: 0, passifs: 0, detracteurs: 0 } })
    renderScreen()
    expect(await screen.findByTestId('nps-score-vide')).toBeInTheDocument()
  })
})
