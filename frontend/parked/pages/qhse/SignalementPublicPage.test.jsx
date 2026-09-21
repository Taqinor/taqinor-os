import { describe, it, expect, vi, afterEach, beforeAll } from 'vitest'
import { render, screen, cleanup, fireEvent, waitFor } from '@testing-library/react'
import { MemoryRouter, Route, Routes } from 'react-router-dom'

/* WIR214 — page publique de signalement chantier QHSE via QR, sans login.
   GET valide le jeton (payload {valide, libelle}), POST enregistre le
   signalement (patron EquipementSignalerPage/XSAV19). api (axios) mocké. */

beforeAll(() => {
  if (typeof globalThis.ResizeObserver === 'undefined') {
    globalThis.ResizeObserver = class {
      observe() {}
      unobserve() {}
      disconnect() {}
    }
  }
  if (typeof Element.prototype.hasPointerCapture === 'undefined') {
    Element.prototype.hasPointerCapture = () => false
  }
  if (typeof Element.prototype.scrollIntoView === 'undefined') {
    Element.prototype.scrollIntoView = () => {}
  }
})

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
  it('affiche le formulaire hors session quand le jeton est valide', async () => {
    api.get.mockResolvedValueOnce({ data: { valide: true, libelle: 'Chantier Anfa' } })
    renderPage()

    expect(await screen.findByText(/Chantier Anfa/)).toBeInTheDocument()
    expect(api.get).toHaveBeenCalledWith('/qhse/public/signalement/qhse-tok-1/')
    expect(screen.getByLabelText('Description')).toBeInTheDocument()
  })

  it('envoie le signalement et affiche la référence créée', async () => {
    api.get.mockResolvedValueOnce({ data: { valide: true, libelle: 'Chantier Anfa' } })
    api.post.mockResolvedValueOnce({ data: { id: 77 } })
    renderPage()

    await screen.findByLabelText('Description')
    fireEvent.change(screen.getByLabelText('Description'), {
      target: { value: 'Échafaudage instable côté nord.' },
    })
    fireEvent.click(screen.getByRole('button', { name: 'Envoyer le signalement' }))

    await waitFor(() => expect(api.post).toHaveBeenCalledTimes(1))
    const [url, body] = api.post.mock.calls[0]
    expect(url).toBe('/qhse/public/signalement/qhse-tok-1/')
    expect(body).toEqual(expect.objectContaining({
      type_signalement: 'danger',
      description: 'Échafaudage instable côté nord.',
    }))

    expect(await screen.findByText(/77/)).toBeInTheDocument()
  })

  it('affiche un message honnête si le jeton est révoqué/inconnu (404 au chargement)', async () => {
    api.get.mockRejectedValueOnce({ response: { status: 404 } })
    renderPage('revoked-token')

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'introuvable ou a été révoqué')
  })

  it('désactive le bouton tant que la description est vide', async () => {
    api.get.mockResolvedValueOnce({ data: { valide: true, libelle: '' } })
    renderPage()
    await screen.findByLabelText('Description')
    expect(screen.getByRole('button', { name: 'Envoyer le signalement' })).toBeDisabled()
  })
})
