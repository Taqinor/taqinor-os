import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'

/* WR11 — FG81 (première réponse SLA) + FG86 (lien de suivi client copiable,
   sans prix). savApi mocké. */

vi.mock('../../api/savApi', () => ({
  default: {
    premierReponseTicket: vi.fn(() => Promise.resolve({
      data: { id: 3, date_premiere_reponse: '2026-06-28T10:00:00Z' },
    })),
    lienClientTicket: vi.fn(() => Promise.resolve({
      data: { token: 'abc', url: 'https://api.taqinor.ma/api/django/public/sav/ticket/abc/' },
    })),
  },
}))

import savApi from '../../api/savApi'
import TicketSuiviClientPanel from './TicketSuiviClientPanel'

afterEach(() => { cleanup(); vi.clearAllMocks() })

describe('TicketSuiviClientPanel (WR11 — FG81/FG86)', () => {
  it('enregistre la première réponse et remonte le ticket mis à jour', async () => {
    const onUpdated = vi.fn()
    render(<TicketSuiviClientPanel
      ticket={{ id: 3, date_premiere_reponse: null }} onUpdated={onUpdated} />)
    fireEvent.click(
      screen.getByRole('button', { name: 'Enregistrer la première réponse' }))
    await waitFor(() =>
      expect(savApi.premierReponseTicket).toHaveBeenCalledWith(3))
    await waitFor(() => expect(onUpdated).toHaveBeenCalledWith(
      expect.objectContaining({ date_premiere_reponse: '2026-06-28T10:00:00Z' })))
  })

  it('affiche la date déjà posée sans bouton (idempotence)', () => {
    render(<TicketSuiviClientPanel
      ticket={{ id: 3, date_premiere_reponse: '2026-06-28T10:00:00Z' }} />)
    expect(screen.queryByRole('button',
      { name: 'Enregistrer la première réponse' })).not.toBeInTheDocument()
    expect(screen.getByText('Première réponse :')).toBeInTheDocument()
  })

  it('génère le lien de suivi client et le rend copiable', async () => {
    render(<TicketSuiviClientPanel ticket={{ id: 3 }} />)
    fireEvent.click(screen.getByRole('button', { name: /Générer le lien de suivi/ }))
    await waitFor(() => expect(savApi.lienClientTicket).toHaveBeenCalledWith(3))
    const input = await screen.findByLabelText('Lien de suivi client')
    expect(input).toHaveValue('https://api.taqinor.ma/api/django/public/sav/ticket/abc/')
    expect(screen.getByRole('button', { name: /Copier/ })).toBeInTheDocument()
  })
})
