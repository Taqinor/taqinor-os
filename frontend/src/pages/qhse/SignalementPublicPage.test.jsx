import { describe, it, expect, vi, afterEach } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* WIR214 — page publique « Signalement chantier » via QR QHSE (XQHS16), sans
   login. Route /qhse/signalement/:token — le token doit rester en phase avec
   `apps/qhse/services.py:generer_qr_signalement`. api (axios) mocké. */

vi.mock('../../api/axios', () => ({
  default: { get: vi.fn(), post: vi.fn() },
}))

import api from '../../api/axios'
import SignalementPublicPage from './SignalementPublicPage'

afterEach(() => { cleanup(); vi.clearAllMocks() })

const renderPage = (token = 'qhse-tok-1') => render(
  <MemoryRouter initialEntries={[`/qhse/signalement/${token}`]}>
    <Routes>
      <Route path="/qhse/signalement/:token" element={<SignalementPublicPage />} />
    </Routes>
  </MemoryRouter>,
)

describe('SignalementPublicPage (public, WIR214)', () => {
  it('vérifie le lien au montage (GET) puis envoie le signalement (POST)', async () => {
    api.get.mockResolvedValueOnce({ data: { valide: true, libelle: 'Chantier Anfa' } })
    api.post.mockResolvedValueOnce({ data: { detail: 'ok', id: 5 } })
    renderPage('qhse-tok-1')

    await waitFor(() => expect(api.get).toHaveBeenCalledWith('/qhse/public/signalement/qhse-tok-1/'))
    expect(await screen.findByText('Chantier Anfa')).toBeInTheDocument()

    fireEvent.click(screen.getByLabelText('Incident'))
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Câble électrique dénudé au sol.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, body] = api.post.mock.calls[0]
    expect(url).toBe('/qhse/public/signalement/qhse-tok-1/')
    expect(body).toMatchObject({
      type_signalement: 'incident', description: 'Câble électrique dénudé au sol.',
    })

    expect(await screen.findByText(/votre signalement a bien été enregistré/)).toBeInTheDocument()
  })

  it('affiche un message honnête si le lien est révoqué (GET 404)', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404 } })
    renderPage('bad-token')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'introuvable ou a été révoqué')
  })

  it('désactive le bouton tant que la description est vide', async () => {
    api.get.mockResolvedValueOnce({ data: { valide: true, libelle: '' } })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Envoyer le signalement' }))
      .toBeDisabled()
  })
})
