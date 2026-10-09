import { describe, it, expect, vi, afterEach } from 'vitest'
import { screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* ASAV32 — sous-notes CSAT sur la page publique quand csat_detaille_actif. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../../api/axios'
import { renderSuiviPage as renderPage } from './__testutils__/renderSuiviPage.jsx'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const ticket = (actif) => ({
  data: {
    reference: 'SAV-9', statut: 'resolu', statut_display: 'Résolu',
    csat_detaille_actif: actif, annule: false, fusionne_dans_reference: null,
  },
})

describe('TicketSuiviPage ASAV32', () => {
  it('réglage actif : trois sélecteurs et POST avec sous_notes', async () => {
    api.get.mockResolvedValueOnce(ticket(true))
    api.post.mockResolvedValueOnce({ data: { note: 4 } })
    renderPage()
    await screen.findByText('SAV-9')
    expect(screen.getByLabelText('Rapidité (optionnel)')).toBeInTheDocument()
    expect(screen.getByLabelText('Courtoisie (optionnel)')).toBeInTheDocument()
    expect(screen.getByLabelText('Résolution (optionnel)')).toBeInTheDocument()
    fireEvent.click(screen.getByRole('button', { name: '4 étoiles' }))
    fireEvent.change(screen.getByLabelText('Rapidité (optionnel)'), { target: { value: '5' } })
    fireEvent.change(screen.getByLabelText('Courtoisie (optionnel)'), { target: { value: '3' } })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/public/sav/ticket/tok/satisfaction/',
      { note: 4, commentaire: undefined, sous_notes: { rapidite: 5, courtoisie: 3 } }))
  })

  it('réglage inactif : formulaire actuel, aucune sous-note', async () => {
    api.get.mockResolvedValueOnce(ticket(false))
    api.post.mockResolvedValueOnce({ data: { note: 4 } })
    renderPage()
    await screen.findByText('SAV-9')
    expect(screen.queryByLabelText('Rapidité (optionnel)')).toBeNull()
    fireEvent.click(screen.getByRole('button', { name: '4 étoiles' }))
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer ma réponse' }))
    await waitFor(() => expect(api.post).toHaveBeenCalledWith(
      '/public/sav/ticket/tok/satisfaction/', { note: 4, commentaire: undefined }))
  })
})
