import { describe, it, expect, vi, beforeEach } from 'vitest'
import { render, screen, waitFor, fireEvent } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'

/* PACT106 — Avis clients + routage Google Reviews (AvisClientViewSet,
   /marketing/avis-clients/ ; actions recevoir/pousser_google). Forme mockée
   = exactement AvisClientSerializer (id/client_id/note/temoignage/statut/
   google_review_url/date_creation). Doctrine NO-OP : pousser_google renvoie
   l'avis INCHANGÉ (jamais une erreur) quand GOOGLE_REVIEW_URL n'est pas
   configuré côté serveur — le bouton reste actionnable, neutre. */

const mocks = vi.hoisted(() => ({ list: vi.fn(), create: vi.fn(), recevoir: vi.fn(), pousserGoogle: vi.fn() }))

vi.mock('../../api/marketingApi', () => ({
  default: {
    unwrapList: (res) => {
      const data = res?.data
      return Array.isArray(data) ? data : (data?.results || [])
    },
    avisClients: {
      list: mocks.list, create: mocks.create,
      recevoir: mocks.recevoir, pousserGoogle: mocks.pousserGoogle,
    },
  },
}))

import AvisClients from './AvisClients'

const renderScreen = () => render(<MemoryRouter><AvisClients /></MemoryRouter>)

beforeEach(() => {
  vi.clearAllMocks()
  mocks.list.mockResolvedValue({ data: [
    { id: 1, client_id: 501, note: null, temoignage: '', statut: 'sollicite',
      google_review_url: '', date_creation: '2026-08-01T09:00:00Z' },
    { id: 2, client_id: 502, note: 5, temoignage: 'Installation impeccable',
      statut: 'recu', google_review_url: '', date_creation: '2026-07-28T09:00:00Z' },
  ] })
  mocks.create.mockResolvedValue({ data: { id: 3 } })
  mocks.recevoir.mockResolvedValue({ data: {
    id: 1, client_id: 501, note: 5, temoignage: 'Très satisfait', statut: 'recu',
    google_review_url: '', date_creation: '2026-08-01T09:00:00Z',
  } })
  mocks.pousserGoogle.mockResolvedValue({ data: {
    id: 2, client_id: 502, note: 5, temoignage: 'Installation impeccable',
    statut: 'recu', google_review_url: '', date_creation: '2026-07-28T09:00:00Z',
  } })
})

describe('AvisClients (PACT106)', () => {
  it('affiche les avis existants avec leur statut réel', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    expect(await screen.findByText('Client #501')).toBeInTheDocument()
    expect(screen.getByText('Client #502')).toBeInTheDocument()
    expect(screen.getByText('Installation impeccable')).toBeInTheDocument()
    expect(screen.getAllByTestId('avis-row').length).toBe(2)
  })

  it('sollicite un nouvel avis pour un client', async () => {
    renderScreen()
    await waitFor(() => expect(mocks.list).toHaveBeenCalled())
    fireEvent.change(screen.getByTestId('avis-client-id'), { target: { value: '777' } })
    fireEvent.click(screen.getByText('Solliciter un avis'))
    await waitFor(() => expect(mocks.create).toHaveBeenCalledWith({ client_id: 777 }))
  })

  it('enregistre un avis reçu (note + témoignage) pour un avis sollicité', async () => {
    renderScreen()
    await screen.findAllByTestId('avis-row')
    fireEvent.click(screen.getByTestId('avis-recevoir-1'))
    fireEvent.change(screen.getByTestId('avis-note-1'), { target: { value: '4' } })
    fireEvent.change(screen.getByTestId('avis-temoignage-1'), { target: { value: 'Très satisfait' } })
    fireEvent.click(screen.getByTestId('avis-recevoir-confirm-1'))
    await waitFor(() => expect(mocks.recevoir).toHaveBeenCalledWith(
      1, { note: 4, temoignage: 'Très satisfait' }))
    // Le badge de statut vient de la réponse SERVEUR (recu), pas d'un calcul client.
    await waitFor(() => expect(screen.getAllByTestId('avis-row')[0]).toHaveTextContent('Reçu'))
  })

  it('un avis déjà reçu n\'a plus de bouton « Avis reçu »', async () => {
    renderScreen()
    await screen.findAllByTestId('avis-row')
    expect(screen.queryByTestId('avis-recevoir-2')).toBeNull()
  })

  it('« Pousser vers Google » reste neutre (avis inchangé) quand le lien n\'est pas configuré', async () => {
    renderScreen()
    await screen.findAllByTestId('avis-row')
    fireEvent.click(screen.getByTestId('avis-pousser-google-2'))
    await waitFor(() => expect(mocks.pousserGoogle).toHaveBeenCalledWith(2))
    // Aucune erreur affichée : la réponse serveur (NO-OP) est rendue telle quelle.
    expect(screen.queryByTestId('avis-err')).toBeNull()
    expect(screen.getAllByTestId('avis-row')[1]).toHaveTextContent('Reçu')
  })

  it('« Pousser vers Google » reflète le routage quand le lien EST configuré côté serveur', async () => {
    mocks.pousserGoogle.mockResolvedValue({ data: {
      id: 2, client_id: 502, note: 5, temoignage: 'Installation impeccable',
      statut: 'publie_google', google_review_url: 'https://g.page/r/exemple/review',
      date_creation: '2026-07-28T09:00:00Z',
    } })
    renderScreen()
    await screen.findAllByTestId('avis-row')
    fireEvent.click(screen.getByTestId('avis-pousser-google-2'))
    await waitFor(() =>
      expect(screen.getAllByTestId('avis-row')[1]).toHaveTextContent('Routé vers Google'))
    expect(screen.getByText('Voir le lien')).toHaveAttribute(
      'href', 'https://g.page/r/exemple/review')
  })
})
