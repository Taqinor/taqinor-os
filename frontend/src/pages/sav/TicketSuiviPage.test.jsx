import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* XSAV10/FG86 — page publique de suivi (statut) + enquête CSAT, sans login.
   api (axios) mocké. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../../api/axios'
import TicketSuiviPage from './TicketSuiviPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = (token = 'tok-1') => render(
  <MemoryRouter initialEntries={[`/suivi/${token}`]}>
    <Routes>
      <Route path="/suivi/:token" element={<TicketSuiviPage />} />
    </Routes>
  </MemoryRouter>,
)

describe('TicketSuiviPage (public, XSAV10/FG86)', () => {
  it('affiche le statut public du ticket résolu par token', async () => {
    api.get.mockResolvedValueOnce({
      data: {
        reference: 'SAV-2026-001', statut: 'en_cours',
        statut_display: 'En cours', date_modification: '2026-07-01T10:00:00Z',
      },
    })
    renderPage('tok-1')
    expect(api.get).toHaveBeenCalledWith('/public/sav/ticket/tok-1/')
    expect(await screen.findByText('SAV-2026-001')).toBeInTheDocument()
    expect(screen.getByText('En cours')).toBeInTheDocument()
  })

  it("affiche un message honnête si le lien est invalide", async () => {
    api.get.mockRejectedValueOnce({
      response: { status: 404, data: { detail: 'Introuvable.' } },
    })
    renderPage('bad-token')
    expect(await screen.findByRole('alert')).toHaveTextContent('Introuvable.')
  })

  it('propose le CSAT pour un ticket résolu et envoie la note', async () => {
    api.get.mockResolvedValueOnce({
      data: { reference: 'SAV-2', statut: 'resolu', statut_display: 'Résolu' },
    })
    api.post.mockResolvedValueOnce({ data: { note: 5, commentaire: '' } })
    renderPage('tok-2')
    await screen.findByText('SAV-2')
    fireEvent.click(screen.getByRole('button', { name: '5 étoiles' }))
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/public/sav/ticket/tok-2/satisfaction/', { note: 5, commentaire: undefined }))
    expect(await screen.findByText('Merci pour votre retour !')).toBeInTheDocument()
  })

  it('ne propose pas le CSAT pour un ticket non résolu', async () => {
    api.get.mockResolvedValueOnce({
      data: { reference: 'SAV-3', statut: 'nouveau', statut_display: 'Nouveau' },
    })
    renderPage('tok-3')
    await screen.findByText('SAV-3')
    expect(screen.queryByRole('radiogroup')).not.toBeInTheDocument()
  })
})
